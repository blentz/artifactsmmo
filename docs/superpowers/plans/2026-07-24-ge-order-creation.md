# Grand Exchange Order-Creation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the GOAP planner POST its own Grand Exchange buy and sell orders (not just fill standing ones), with tracked-escrow state, fail-closed anchored pricing, on-need+TTL cancellation, and a bid-vs-craft mutual exclusion.

**Architecture:** A shared order-state core (`WorldState.open_orders` + escrow in `apply()`, reconciled against the API each cycle) plus two symmetric legs. Pricing and the extended FILL/POST/NPC venue choice are pure functions mirrored in Lean (extending the existing `LiquidationVenue`/`BuySourceVenue` proofs). Buy-posting is a reactive discretionary means, gated by a pure `bid_vs_craft` estimator that refuses to bid when self-crafting is faster.

**Tech Stack:** Python 3.13, `uv`, pytest, dataclasses (`frozen=True` `WorldState`), Lean 4 + mathlib (`formal/`), generated `artifactsmmo_api_client`.

## Global Constraints

- `uv run` prefix on ALL Python commands (`uv run pytest`, `uv run mypy`).
- One behavioral class per file. Absolute imports only; no inline imports; no `...` imports; no `if TYPE_CHECKING`.
- Never catch `Exception`. Multiple levels of error handling is a bug.
- Use only API data or fail with an error — no defaulting over missing game data.
- Test success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage on new code. Tests live in `tests/`.
- New decision logic must be Lean-proven AND pass the differential + mutation gate (formal-development skill). No vacuous theorems.
- Green tests ≠ runtime-active: venue/pricing/goal changes must fire on a live `plan <char>` before "done".
- New `MeansKind`/`GuardKind` requires `DecideKey.lean` + Oracle + `decide_key` updated in lockstep (append enum members LAST to keep oracle index dispatch + diff `_MEANS_INDEX` stable).
- Deterministic ordering only — no `repr`/`str`/alphabetical tiebreaks. Order `open_orders` by `(side, code, price, id)`.

## Build order rationale

Tasks 1–4 build the pure, provable core (state + pricing + Lean) with no behavior change. Tasks 5–8 add the actions and reconciliation. Tasks 9–10 add the bid-vs-craft gate and suppression. Tasks 11–13 wire triggers into the arbiter. Tasks 14–15 close the formal contract and verify runtime activation. Each task ends green and committed.

---

### Task 1: `OpenOrder` type + `WorldState.open_orders` field (state carries through, no behavior)

**Files:**
- Create: `src/artifactsmmo_cli/ai/open_order.py`
- Modify: `src/artifactsmmo_cli/ai/world_state.py` (add field ~after `layer`; thread through `from_character_schema` ~210-302)
- Test: `tests/test_ai/test_open_order_state.py`

**Interfaces:**
- Produces: `OpenOrder` = `NamedTuple(id:str, code:str, qty:int, price:int, side:OrderSide, age:int)`; `OrderSide` enum `{BUY, SELL}`; `WorldState.open_orders: tuple[OpenOrder, ...] = ()`.
- Consumes: nothing.

Rationale: `open_orders` is a NEW field with an immutable default `()` — it must go in the **defaulted** block (after `bank_capacity`/`layer`), NOT among the required positional fields where `pending_items` sits.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_open_order_state.py
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from tests.test_ai.fixtures import make_state


def test_open_orders_defaults_empty():
    state = make_state()
    assert state.open_orders == ()


def test_open_orders_carries_order_records():
    order = OpenOrder(id="ord-1", code="iron_ore", qty=5, price=9, side=OrderSide.SELL, age=0)
    state = make_state(open_orders=(order,))
    assert state.open_orders[0].code == "iron_ore"
    assert state.open_orders[0].side is OrderSide.SELL


def test_open_order_is_frozen_namedtuple():
    order = OpenOrder(id="o", code="c", qty=1, price=1, side=OrderSide.BUY, age=0)
    import pytest
    with pytest.raises(AttributeError):
        order.qty = 2  # NamedTuple is immutable
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_open_order_state.py -v`
Expected: FAIL — `ModuleNotFoundError: artifactsmmo_cli.ai.open_order` (and `make_state` rejects `open_orders`).

- [ ] **Step 3: Create the `OpenOrder` type**

```python
# src/artifactsmmo_cli/ai/open_order.py
"""Posted Grand Exchange order state: a frozen record of one open (buy or sell)
order the character has posted, with the age (in cycles) used by the TTL cancel."""

from enum import Enum
from typing import NamedTuple


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OpenOrder(NamedTuple):
    id: str
    code: str
    qty: int
    price: int
    side: OrderSide
    age: int
```

- [ ] **Step 4: Add the field to `WorldState`**

In `src/artifactsmmo_cli/ai/world_state.py`, add the import at the top:

```python
from artifactsmmo_cli.ai.open_order import OpenOrder
```

Add the field in the DEFAULTED block (place it immediately after `layer: str = "overworld"`):

```python
    open_orders: tuple[OpenOrder, ...] = ()
    """Posted GE orders the character currently has open. Empty tuple = none.
    Escrow: a posted SELL removes the item from `inventory`; a posted BUY removes
    `gold`. Settlement (fill) is reconciled from the API each cycle. Ordered
    deterministically by (side, code, price, id) at construction sites."""
```

Thread it through `from_character_schema` (add a keyword parameter defaulting to `()` and pass it into the constructor, mirroring how `pending_items` is threaded):

```python
    # in from_character_schema signature, alongside pending_items=...:
        open_orders: tuple[OpenOrder, ...] = (),
    # ... and in the WorldState(...) construction inside that method:
        open_orders=open_orders,
```

- [ ] **Step 5: Update the `make_state` fixture to accept `open_orders`**

In `tests/test_ai/fixtures.py`, add `open_orders: tuple = ()` to the `make_state` signature and pass it to the `WorldState(...)` (or `dataclasses.replace`) it builds. (Follow the existing pattern that fixture uses for optional fields.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_open_order_state.py -v`
Expected: PASS (3 passed).

- [ ] **Step 7: Verify existing state tests still green + type-check**

Run: `uv run pytest tests/test_ai/ -k world_state -q && uv run mypy src/artifactsmmo_cli/ai/world_state.py src/artifactsmmo_cli/ai/open_order.py`
Expected: PASS, no mypy errors.

- [ ] **Step 8: Commit**

```bash
git add src/artifactsmmo_cli/ai/open_order.py src/artifactsmmo_cli/ai/world_state.py tests/test_ai/test_open_order_state.py tests/test_ai/fixtures.py
git commit -m "feat(ge): add OpenOrder type + WorldState.open_orders escrow field"
```

---

### Task 2: Pure post-pricing module (`ge_post_pricing.py`)

**Files:**
- Create: `src/artifactsmmo_cli/ai/ge_post_pricing.py`
- Test: `tests/test_ai/test_ge_post_pricing.py`

**Interfaces:**
- Produces:
  - `sell_post_price(best_sell: int | None, npc_sellback: int, margin: int) -> int | None`
  - `buy_post_price(best_buy: int | None, alt_cost: int, margin: int) -> int | None`
- Consumes: nothing (pure ints/Options). Mirrors `liquidation_venue.py`/`buy_source_venue.py` style.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_ge_post_pricing.py
from artifactsmmo_cli.ai.ge_post_pricing import sell_post_price, buy_post_price


class TestSellPostPrice:
    def test_no_anchor_returns_none(self):
        assert sell_post_price(None, npc_sellback=5, margin=1) is None

    def test_undercuts_best_sell_by_one_tick(self):
        assert sell_post_price(best_sell=20, npc_sellback=5, margin=1) == 19

    def test_floored_at_npc_sellback_plus_margin(self):
        # best_sell-1 = 5 would sit below the floor 6; clamp up to the floor.
        assert sell_post_price(best_sell=6, npc_sellback=5, margin=1) == 6


class TestBuyPostPrice:
    def test_no_anchor_returns_none(self):
        assert buy_post_price(None, alt_cost=15, margin=1) is None

    def test_overbids_best_buy_by_one_tick(self):
        assert buy_post_price(best_buy=8, alt_cost=15, margin=1) == 9

    def test_ceilinged_at_alt_cost_minus_margin(self):
        # best_buy+1 = 15 would sit above the ceiling 14; clamp down to the ceiling.
        assert buy_post_price(best_buy=14, alt_cost=15, margin=1) == 14
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_ge_post_pricing.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/artifactsmmo_cli/ai/ge_post_pricing.py
"""Pure price-setting for POSTED Grand Exchange orders — the speculative half
deliberately left out of liquidation_venue / buy_source_venue, made safe by two
guards: (1) FAIL CLOSED with no live anchor (best-order is None -> None -> no post),
so an empty book never yields a speculative price; (2) FLOOR/CEILING BOUND against
the realizable alternative, so a posted price can never be worse than dumping to /
buying from the NPC. Undercut/overbid by ONE tick to sit in front of the queue.

These are the differential target proved in formal/Formal/GePostPricing.lean.
"""


def sell_post_price(best_sell: int | None, npc_sellback: int, margin: int) -> int | None:
    """Price to post a SELL order at: one tick below the best standing sell order,
    but never below the NPC sell-back floor plus margin. None (no post) when there
    is no standing sell order to anchor on."""
    if best_sell is None:
        return None
    return max(best_sell - 1, npc_sellback + margin)


def buy_post_price(best_buy: int | None, alt_cost: int, margin: int) -> int | None:
    """Price to post a BUY order at: one tick above the best standing buy order, but
    never above the realizable alternative cost (NPC buy / fillable sell order) minus
    margin. None (no post) when there is no standing buy order to anchor on."""
    if best_buy is None:
        return None
    return min(best_buy + 1, alt_cost - margin)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_ge_post_pricing.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/ge_post_pricing.py tests/test_ai/test_ge_post_pricing.py
git commit -m "feat(ge): pure fail-closed floor-bounded post-pricing"
```

---

### Task 3: Lean model for post-pricing (`formal/Formal/GePostPricing.lean`)

**Files:**
- Create: `formal/Formal/GePostPricing.lean`
- Modify: `formal/Formal.lean` (add `import Formal.GePostPricing`)
- Test: `lake build`

**Interfaces:**
- Produces: `sellPostPrice`, `buyPostPrice` (Lean mirrors) + dominance/fail-closed theorems. Mirrors the namespace + header-pragma convention of `LiquidationVenue.lean`.

Use the lean4 / formal-development skill to discharge the proofs. The statements below are the contract — do NOT weaken them.

- [ ] **Step 1: Write the Lean definitions + theorem statements**

```lean
-- formal/Formal/GePostPricing.lean
-- @concept: grandexchange @property: fail_closed, dominance, undercut
import Mathlib.Data.Int.Order.Basic

namespace Formal.GePostPricing

/-- Post price for a SELL order: one tick below the best standing sell, floored at
the NPC sell-back plus margin. `none` (no anchor) -> `none`. Mirrors Python. -/
def sellPostPrice (bestSell : Option Int) (npcSellback margin : Int) : Option Int :=
  match bestSell with
  | some b => some (max (b - 1) (npcSellback + margin))
  | none => none

/-- Post price for a BUY order: one tick above the best standing buy, capped at the
alternative cost minus margin. `none` (no anchor) -> `none`. Mirrors Python. -/
def buyPostPrice (bestBuy : Option Int) (altCost margin : Int) : Option Int :=
  match bestBuy with
  | some b => some (min (b + 1) (altCost - margin))
  | none => none

/-- FAIL CLOSED: no standing sell order -> no posted price. -/
theorem sell_none_of_no_anchor (npcSellback margin : Int) :
    sellPostPrice none npcSellback margin = none := rfl

/-- FAIL CLOSED: no standing buy order -> no posted price. -/
theorem buy_none_of_no_anchor (altCost margin : Int) :
    buyPostPrice none altCost margin = none := rfl

/-- DOMINANCE (sell): a posted sell price is never below the NPC floor+margin, so
posting weakly dominates dumping to the NPC. -/
theorem sell_price_ge_floor (b npcSellback margin : Int) :
    ∀ p, sellPostPrice (some b) npcSellback margin = some p → npcSellback + margin ≤ p

/-- DOMINANCE (buy): a posted buy price is never above the alt-cost minus margin, so
posting weakly dominates buying from the alternative. -/
theorem buy_price_le_ceiling (b altCost margin : Int) :
    ∀ p, buyPostPrice (some b) altCost margin = some p → p ≤ altCost - margin

/-- UNDERCUT (sell): the posted price never exceeds one tick below the best sell. -/
theorem sell_price_le_best_minus_one (b npcSellback margin : Int) :
    ∀ p, sellPostPrice (some b) npcSellback margin = some p → p ≤ b - 1 ∨ p = npcSellback + margin

/-- OVERBID (buy): the posted price is at least one tick above the best buy (or the cap). -/
theorem buy_price_ge_best_plus_one (b altCost margin : Int) :
    ∀ p, buyPostPrice (some b) altCost margin = some p → b + 1 ≤ p ∨ p = altCost - margin

example : sellPostPrice (some 20) 5 1 = some 19 := by decide
example : sellPostPrice (some 6) 5 1 = some 6 := by decide
example : sellPostPrice none 5 1 = none := by decide
example : buyPostPrice (some 8) 15 1 = some 9 := by decide
example : buyPostPrice (some 14) 15 1 = some 14 := by decide
example : buyPostPrice none 15 1 = none := by decide

end Formal.GePostPricing
```

- [ ] **Step 2: Add the import to the formal root**

Add `import Formal.GePostPricing` to `formal/Formal.lean` (alongside the existing `import Formal.LiquidationVenue`).

- [ ] **Step 3: Build and discharge proofs**

Run: `cd formal && lake build 2>&1 | tail -20`
Expected: FAIL initially with `sorry`/unfinished goals on the theorem bodies. Use lean4:prove (or formal-development) to fill each theorem. The `example ... := by decide` lines and the two `rfl` theorems should pass immediately.

- [ ] **Step 4: Verify green build + no axioms/sorries**

Run: `cd formal && lake build && grep -rn "sorry" Formal/GePostPricing.lean || echo "no sorries"`
Expected: build succeeds; "no sorries".

- [ ] **Step 5: Commit**

```bash
git add formal/Formal/GePostPricing.lean formal/Formal.lean
git commit -m "feat(ge): Lean model for post-pricing (fail-closed + dominance)"
```

---

### Task 4: Extend venue deciders to 3-way FILL/POST/NPC (Python + Lean)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/liquidation_venue.py` (add `Venue.GE_POST` + `choose_venue3`)
- Modify: `src/artifactsmmo_cli/ai/buy_source_venue.py` (add `BuyVenue.GE_POST` + `choose_buy_venue3`)
- Modify: `formal/Formal/LiquidationVenue.lean`, `formal/Formal/BuySourceVenue.lean` (mirror the 3-way)
- Test: `tests/test_ai/test_liquidation_venue.py`, `tests/test_ai/test_buy_source_venue.py`

**Interfaces:**
- Produces:
  - `Venue.GE_POST`; `choose_venue3(npc_pay: int, ge_fill_proceeds: int | None, post_price: int | None) -> Venue`
  - `BuyVenue.GE_POST`; `choose_buy_venue3(npc_price: int, ge_fill_cost: int | None, post_price: int | None) -> BuyVenue`
- Consumes: `sell_post_price`/`buy_post_price` (Task 2) at call sites for `post_price`.

Rule (sell): prefer FILL (`GE`) if a fillable buy order pays ≥ post_price; elif post_price > npc_pay → `GE_POST`; else NPC. Symmetric for buy (min cost).

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_ai/test_liquidation_venue.py
from artifactsmmo_cli.ai.liquidation_venue import choose_venue3, Venue


class TestChooseVenue3:
    def test_fill_preferred_when_order_pays_at_least_post(self):
        # standing buy order pays 20, post would be 18 -> fill now.
        assert choose_venue3(npc_pay=5, ge_fill_proceeds=20, post_price=18) is Venue.GE

    def test_post_when_post_beats_npc_and_no_good_fill(self):
        # no fillable order, post 18 > npc 5 -> post.
        assert choose_venue3(npc_pay=5, ge_fill_proceeds=None, post_price=18) is Venue.GE_POST

    def test_npc_when_no_post_anchor(self):
        assert choose_venue3(npc_pay=5, ge_fill_proceeds=None, post_price=None) is Venue.NPC

    def test_npc_when_post_not_better_than_npc(self):
        assert choose_venue3(npc_pay=20, ge_fill_proceeds=None, post_price=18) is Venue.NPC
```

```python
# append to tests/test_ai/test_buy_source_venue.py
from artifactsmmo_cli.ai.buy_source_venue import choose_buy_venue3, BuyVenue


class TestChooseBuyVenue3:
    def test_fill_preferred_when_order_costs_at_most_post(self):
        assert choose_buy_venue3(npc_price=20, ge_fill_cost=8, post_price=10) is BuyVenue.GE

    def test_post_when_post_beats_npc_and_no_good_fill(self):
        assert choose_buy_venue3(npc_price=20, ge_fill_cost=None, post_price=10) is BuyVenue.GE_POST

    def test_npc_when_no_post_anchor(self):
        assert choose_buy_venue3(npc_price=20, ge_fill_cost=None, post_price=None) is BuyVenue.NPC

    def test_npc_when_post_not_cheaper_than_npc(self):
        assert choose_buy_venue3(npc_price=8, ge_fill_cost=None, post_price=10) is BuyVenue.NPC
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_liquidation_venue.py::TestChooseVenue3 tests/test_ai/test_buy_source_venue.py::TestChooseBuyVenue3 -v`
Expected: FAIL — `ImportError: cannot import name 'choose_venue3'`.

- [ ] **Step 3: Extend the sell decider**

In `src/artifactsmmo_cli/ai/liquidation_venue.py`, add the enum member and function:

```python
class Venue(Enum):
    NPC = "npc"
    GE = "ge"           # fill a standing buy order (immediate)
    GE_POST = "ge_post"  # post our own sell order (deferred)


def choose_venue3(npc_pay: int, ge_fill_proceeds: int | None, post_price: int | None) -> Venue:
    """Three-way sell venue. FILL an existing buy order when it pays at least our
    post price (immediate beats deferred at equal terms). Else POST our own sell
    order when its price beats the NPC floor. Else NPC. `post_price is None` is the
    fail-closed anchor guard (no book to anchor on)."""
    if ge_fill_proceeds is not None and post_price is not None and ge_fill_proceeds >= post_price:
        return Venue.GE
    if ge_fill_proceeds is not None and post_price is None and ge_fill_proceeds > npc_pay:
        return Venue.GE
    if post_price is not None and post_price > npc_pay:
        return Venue.GE_POST
    if ge_fill_proceeds is not None and ge_fill_proceeds > npc_pay:
        return Venue.GE
    return Venue.NPC
```

- [ ] **Step 4: Extend the buy decider**

In `src/artifactsmmo_cli/ai/buy_source_venue.py`:

```python
class BuyVenue(Enum):
    NPC = "npc"
    GE = "ge"            # fill a standing sell order (immediate)
    GE_POST = "ge_post"  # post our own buy order (deferred)


def choose_buy_venue3(npc_price: int, ge_fill_cost: int | None, post_price: int | None) -> BuyVenue:
    """Three-way buy venue (dual of choose_venue3). FILL an existing sell order when
    it costs at most our post price. Else POST our own buy order when its price beats
    the NPC cost. Else NPC. `post_price is None` is the fail-closed anchor guard."""
    if ge_fill_cost is not None and post_price is not None and ge_fill_cost <= post_price:
        return BuyVenue.GE
    if ge_fill_cost is not None and post_price is None and ge_fill_cost < npc_price:
        return BuyVenue.GE
    if post_price is not None and post_price < npc_price:
        return BuyVenue.GE_POST
    if ge_fill_cost is not None and ge_fill_cost < npc_price:
        return BuyVenue.GE
    return BuyVenue.NPC
```

- [ ] **Step 5: Run the Python tests**

Run: `uv run pytest tests/test_ai/test_liquidation_venue.py tests/test_ai/test_buy_source_venue.py -v`
Expected: PASS (existing 2-way tests + new 3-way tests all green).

- [ ] **Step 6: Mirror the 3-way in Lean**

Extend `formal/Formal/LiquidationVenue.lean` (add `Venue.gePost`, `chooseVenue3`) and `formal/Formal/BuySourceVenue.lean` (add `BuyVenue.gePost`, `chooseBuyVenue3`) with a totality theorem and a fail-closed theorem:

```lean
-- in Formal.LiquidationVenue
def chooseVenue3 (npcPay : Int) (geFill : Option Int) (postPrice : Option Int) : Venue :=
  match geFill, postPrice with
  | some f, some p => if f ≥ p then Venue.ge else if p > npcPay then Venue.gePost
                      else if f > npcPay then Venue.ge else Venue.npc
  | some f, none   => if f > npcPay then Venue.ge else Venue.npc
  | none,   some p => if p > npcPay then Venue.gePost else Venue.npc
  | none,   none   => Venue.npc

theorem venue3_total (npcPay : Int) (geFill postPrice : Option Int) :
    chooseVenue3 npcPay geFill postPrice = Venue.npc
    ∨ chooseVenue3 npcPay geFill postPrice = Venue.ge
    ∨ chooseVenue3 npcPay geFill postPrice = Venue.gePost

theorem post_requires_anchor (npcPay : Int) (geFill postPrice : Option Int)
    (h : chooseVenue3 npcPay geFill postPrice = Venue.gePost) : postPrice.isSome
```

Add `Venue.gePost` to the `inductive Venue` (and `BuyVenue.gePost`). Provide the dual defs/theorems in `BuySourceVenue.lean`. Discharge with lean4:prove.

- [ ] **Step 7: Build Lean green**

Run: `cd formal && lake build 2>&1 | tail -20`
Expected: PASS, no sorries.

- [ ] **Step 8: Commit**

```bash
git add src/artifactsmmo_cli/ai/liquidation_venue.py src/artifactsmmo_cli/ai/buy_source_venue.py formal/Formal/LiquidationVenue.lean formal/Formal/BuySourceVenue.lean tests/test_ai/test_liquidation_venue.py tests/test_ai/test_buy_source_venue.py
git commit -m "feat(ge): extend venue deciders to 3-way FILL/POST/NPC (py+lean)"
```

---

### Task 5: `GePostSellOrderAction` (escrow apply + create_sell_order execute)

**Files:**
- Create: `src/artifactsmmo_cli/ai/actions/ge_post_sell.py`
- Test: `tests/test_ai/test_actions_ge_post_sell.py`

**Interfaces:**
- Consumes: `OpenOrder`/`OrderSide` (Task 1), `WorldState.open_orders`, `game_data.ge_best_sell_order`, `game_data.grand_exchange_location`.
- Produces: `GePostSellOrderAction(item_code:str, quantity:int, price:int, ge_location:tuple[int,int]|None)`.

Pattern mirrors `GeFillBuyOrderAction` (`ge_fill.py`) but escrows the item and posts via `action_ge_create_sell_order`. The client fn + body: `action_ge_create_sell_order_my_name_action_grandexchange_create_sell_order_post.sync(client=, name=, body=GEOrderCreationSchema(code=, quantity=, price=))`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_actions_ge_post_sell.py
from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.ge_post_sell import GePostSellOrderAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.open_order import OrderSide
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._ge_sell_orders = kwargs.get("ge_sell_orders", {})
    return gd


class TestApplyEscrowsItem:
    def test_apply_removes_item_and_appends_open_sell_order(self):
        a = GePostSellOrderAction(item_code="iron_ore", quantity=3, price=19, ge_location=(5, 1))
        gd = make_gd()
        state = make_state(x=0, y=0, gold=50, inventory={"iron_ore": 5})
        new_state = a.apply(state, gd)
        assert new_state.inventory["iron_ore"] == 2          # item escrowed out of the bag
        assert new_state.gold == 50                          # gold arrives only on fill
        assert len(new_state.open_orders) == 1
        o = new_state.open_orders[0]
        assert (o.code, o.qty, o.price, o.side) == ("iron_ore", 3, 19, OrderSide.SELL)
        assert (new_state.x, new_state.y) == (5, 1)

    def test_apply_raises_when_inventory_insufficient(self):
        a = GePostSellOrderAction(item_code="iron_ore", quantity=9, price=19, ge_location=(5, 1))
        state = make_state(inventory={"iron_ore": 2})
        with pytest.raises(AssertionError):
            a.apply(state, make_gd())


class TestApplicable:
    def test_not_applicable_without_ge_location(self):
        a = GePostSellOrderAction(item_code="iron_ore", quantity=1, price=19, ge_location=None)
        assert a.is_applicable(make_state(inventory={"iron_ore": 1}), make_gd()) is False

    def test_not_applicable_without_item(self):
        a = GePostSellOrderAction(item_code="iron_ore", quantity=1, price=19, ge_location=(5, 1))
        assert a.is_applicable(make_state(inventory={}), make_gd()) is False


class TestExecute:
    def test_execute_moves_then_posts_sell_order(self):
        a = GePostSellOrderAction(item_code="iron_ore", quantity=2, price=19, ge_location=(5, 1))
        char = make_char_schema()
        state = make_state(x=0, y=0, inventory={"iron_ore": 3})
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.ge_post_sell.MoveAction") as MockMove:
            MockMove.return_value.execute.return_value = make_state(x=5, y=1, inventory={"iron_ore": 3})
            with patch("artifactsmmo_cli.ai.actions.ge_post_sell.action_ge_create_sell_order",
                       return_value=make_api_result(char)) as mock_post:
                a.execute(state, client)
        mock_post.assert_called_once()
        body = mock_post.call_args.kwargs["body"]
        assert (body.code, body.quantity, body.price) == ("iron_ore", 2, 19)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_actions_ge_post_sell.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the action**

```python
# src/artifactsmmo_cli/ai/actions/ge_post_sell.py
"""GePostSellOrderAction: POST a new Grand Exchange sell order, escrowing the item.

Unlike GeFillBuyOrderAction (which fills a standing buy order for immediate gold),
posting lists our OWN sell order: the item leaves the inventory now (escrow) and the
gold arrives later when a buyer fills it. Settlement is reconciled from the API each
cycle (see reconciliation). The price is chosen fail-closed and floor-bounded by
ge_post_pricing.sell_post_price at the call site — this action just carries it.
"""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_ge_create_sell_order_my_name_action_grandexchange_create_sell_order_post import (
    sync as action_ge_create_sell_order,
)
from artifactsmmo_api_client.models.ge_order_creation_schema import GEOrderCreationSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class GePostSellOrderAction(Action):
    """Move to the Grand Exchange and post a new sell order, escrowing the item."""

    tags: ClassVar[frozenset[str]] = frozenset({"npc"})

    item_code: str
    quantity: int
    price: int
    ge_location: tuple[int, int] | None = field(default=None, repr=False)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.ge_location is None:
            return False
        return state.inventory.get(self.item_code, 0) >= self.quantity

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        held = state.inventory.get(self.item_code, 0)
        if held < self.quantity:
            raise AssertionError(
                f"GePostSellOrderAction.apply: held={held} < quantity={self.quantity} "
                f"— is_applicable invariant violated"
            )
        new_inventory = dict(state.inventory)
        remaining = held - self.quantity
        if remaining <= 0:
            new_inventory.pop(self.item_code, None)
        else:
            new_inventory[self.item_code] = remaining
        dest = self.ge_location or (state.x, state.y)
        # Optimistic predicted id; reconciliation replaces it with the real id.
        new_order = OpenOrder(
            id=f"pending:{self.item_code}:{self.price}", code=self.item_code,
            qty=self.quantity, price=self.price, side=OrderSide.SELL, age=0,
        )
        new_orders = tuple(sorted(
            (*state.open_orders, new_order),
            key=lambda o: (o.side.value, o.code, o.price, o.id),
        ))
        return dataclasses.replace(
            state, x=dest[0], y=dest[1], inventory=new_inventory,
            open_orders=new_orders, cooldown_expires=None,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.ge_location or (state.x, state.y)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return 2.0 + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.ge_location and (state.x, state.y) != self.ge_location:
            state = MoveAction(x=self.ge_location[0], y=self.ge_location[1]).execute(state, client)
        body = GEOrderCreationSchema(code=self.item_code, quantity=self.quantity, price=self.price)
        result = action_ge_create_sell_order(client=client, name=state.character, body=body)
        result = Action._raise_for_error(
            result, f"GePostSell {self.item_code}×{self.quantity}@{self.price}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items, bank_gold=state.bank_gold,
            pending_items=state.pending_items, active_events=state.active_events,
            raids=state.raids, open_orders=state.open_orders,
        )

    def __repr__(self) -> str:
        return f"GePostSell({self.item_code}×{self.quantity}@{self.price})"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_actions_ge_post_sell.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/ge_post_sell.py tests/test_ai/test_actions_ge_post_sell.py
git commit -m "feat(ge): GePostSellOrderAction with item escrow"
```

---

### Task 6: `GePostBuyOrderAction` (gold escrow + create_buy_order execute)

**Files:**
- Create: `src/artifactsmmo_cli/ai/actions/ge_post_buy.py`
- Test: `tests/test_ai/test_actions_ge_post_buy.py`

**Interfaces:**
- Consumes: `OpenOrder`/`OrderSide`, `reserve_floor` (`ai/progression_reserve.py`), `GEBuyOrderCreationSchema`, `action_ge_create_buy_order_my_name_action_grandexchange_create_buy_order_post`.
- Produces: `GePostBuyOrderAction(item_code:str, quantity:int, price:int, ge_location:tuple[int,int]|None)`.

Mirrors `GeFillSellOrderAction`'s gold/reserve gate, but escrows gold and posts a buy order.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_actions_ge_post_buy.py
from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.ge_post_buy import GePostBuyOrderAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.open_order import OrderSide
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema


def make_gd() -> GameData:
    return GameData()


class TestApplyEscrowsGold:
    def test_apply_removes_gold_and_appends_open_buy_order(self):
        a = GePostBuyOrderAction(item_code="iron_ore", quantity=3, price=9, ge_location=(5, 1))
        state = make_state(x=0, y=0, gold=100, inventory={})
        new_state = a.apply(state, make_gd())
        assert new_state.gold == 73                          # 100 - 3*9
        assert "iron_ore" not in new_state.inventory         # item arrives only on fill
        assert len(new_state.open_orders) == 1
        o = new_state.open_orders[0]
        assert (o.code, o.qty, o.price, o.side) == ("iron_ore", 3, 9, OrderSide.BUY)

    def test_apply_raises_when_gold_insufficient(self):
        a = GePostBuyOrderAction(item_code="iron_ore", quantity=3, price=90, ge_location=(5, 1))
        state = make_state(gold=10)
        with pytest.raises(AssertionError):
            a.apply(state, make_gd())


class TestExecute:
    def test_execute_moves_then_posts_buy_order(self):
        a = GePostBuyOrderAction(item_code="iron_ore", quantity=2, price=9, ge_location=(5, 1))
        char = make_char_schema()
        state = make_state(x=0, y=0, gold=100)
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.ge_post_buy.MoveAction") as MockMove:
            MockMove.return_value.execute.return_value = make_state(x=5, y=1, gold=100)
            with patch("artifactsmmo_cli.ai.actions.ge_post_buy.action_ge_create_buy_order",
                       return_value=make_api_result(char)) as mock_post:
                a.execute(state, client)
        body = mock_post.call_args.kwargs["body"]
        assert (body.code, body.quantity, body.price) == ("iron_ore", 2, 9)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_actions_ge_post_buy.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the action**

```python
# src/artifactsmmo_cli/ai/actions/ge_post_buy.py
"""GePostBuyOrderAction: POST a new Grand Exchange buy order, escrowing the gold.

Dual of GePostSellOrderAction. Gold leaves now (escrow); the item arrives later,
into the character's pending list, when a seller fills the order — reconciled from
the API each cycle. The price is chosen fail-closed and ceiling-bounded by
ge_post_pricing.buy_post_price at the call site. Honours the progression reserve
floor exactly like GeFillSellOrderAction so bidding never starves core spending.
"""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_ge_create_buy_order_my_name_action_grandexchange_create_buy_order_post import (
    sync as action_ge_create_buy_order,
)
from artifactsmmo_api_client.models.ge_buy_order_creation_schema import GEBuyOrderCreationSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from artifactsmmo_cli.ai.progression_reserve import reserve_floor
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class GePostBuyOrderAction(Action):
    """Move to the Grand Exchange and post a new buy order, escrowing the gold."""

    tags: ClassVar[frozenset[str]] = frozenset({"npc"})

    item_code: str
    quantity: int
    price: int
    ge_location: tuple[int, int] | None = field(default=None, repr=False)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.ge_location is None:
            return False
        cost = self.price * self.quantity
        return state.gold - cost >= reserve_floor(state, game_data, self.item_code)

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        cost = self.price * self.quantity
        if state.gold - cost < reserve_floor(state, game_data, self.item_code):
            raise AssertionError(
                f"GePostBuyOrderAction.apply: gold={state.gold} - cost={cost} below "
                f"reserve floor — is_applicable invariant violated"
            )
        dest = self.ge_location or (state.x, state.y)
        new_order = OpenOrder(
            id=f"pending:{self.item_code}:{self.price}", code=self.item_code,
            qty=self.quantity, price=self.price, side=OrderSide.BUY, age=0,
        )
        new_orders = tuple(sorted(
            (*state.open_orders, new_order),
            key=lambda o: (o.side.value, o.code, o.price, o.id),
        ))
        return dataclasses.replace(
            state, gold=state.gold - cost, x=dest[0], y=dest[1],
            open_orders=new_orders, cooldown_expires=None,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.ge_location or (state.x, state.y)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return 2.0 + dist + self.price * self.quantity / 10.0

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.ge_location and (state.x, state.y) != self.ge_location:
            state = MoveAction(x=self.ge_location[0], y=self.ge_location[1]).execute(state, client)
        body = GEBuyOrderCreationSchema(code=self.item_code, quantity=self.quantity, price=self.price)
        result = action_ge_create_buy_order(client=client, name=state.character, body=body)
        result = Action._raise_for_error(
            result, f"GePostBuy {self.item_code}×{self.quantity}@{self.price}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items, bank_gold=state.bank_gold,
            pending_items=state.pending_items, active_events=state.active_events,
            raids=state.raids, open_orders=state.open_orders,
        )

    def __repr__(self) -> str:
        return f"GePostBuy({self.item_code}×{self.quantity}@{self.price})"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_actions_ge_post_buy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/ge_post_buy.py tests/test_ai/test_actions_ge_post_buy.py
git commit -m "feat(ge): GePostBuyOrderAction with gold escrow"
```

---

### Task 7: `GeCancelOrderAction` (reverse escrow + cancel API)

**Files:**
- Create: `src/artifactsmmo_cli/ai/actions/ge_cancel_order.py`
- Test: `tests/test_ai/test_actions_ge_cancel_order.py`

**Interfaces:**
- Consumes: `OpenOrder`/`OrderSide`, `GECancelOrderSchema`, `action_ge_cancel_order_my_name_action_grandexchange_cancel_post`, `WorldState.open_orders`.
- Produces: `GeCancelOrderAction(order_id:str, ge_location:tuple[int,int]|None)`.

Cancel reverses the escrow: SELL → item back to inventory; BUY → gold back. **Live-probe residual:** confirm on first live cancel whether the item returns to `inventory` or `pending_items`; this task models the inventory-return case and the reconciliation task (Task 8) corrects from API truth regardless.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_actions_ge_cancel_order.py
from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.actions.ge_cancel_order import GeCancelOrderAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema


class TestApplyReversesEscrow:
    def test_cancel_sell_returns_item(self):
        order = OpenOrder(id="o1", code="iron_ore", qty=3, price=19, side=OrderSide.SELL, age=2)
        a = GeCancelOrderAction(order_id="o1", ge_location=(5, 1))
        state = make_state(gold=50, inventory={}, open_orders=(order,))
        new_state = a.apply(state, GameData())
        assert new_state.inventory["iron_ore"] == 3
        assert new_state.gold == 50
        assert new_state.open_orders == ()

    def test_cancel_buy_returns_gold(self):
        order = OpenOrder(id="o2", code="iron_ore", qty=3, price=9, side=OrderSide.BUY, age=2)
        a = GeCancelOrderAction(order_id="o2", ge_location=(5, 1))
        state = make_state(gold=50, inventory={}, open_orders=(order,))
        new_state = a.apply(state, GameData())
        assert new_state.gold == 77                          # 50 + 3*9
        assert new_state.open_orders == ()

    def test_not_applicable_when_order_absent(self):
        a = GeCancelOrderAction(order_id="missing", ge_location=(5, 1))
        assert a.is_applicable(make_state(open_orders=()), GameData()) is False


class TestExecute:
    def test_execute_calls_cancel_api(self):
        order = OpenOrder(id="o1", code="iron_ore", qty=1, price=19, side=OrderSide.SELL, age=1)
        a = GeCancelOrderAction(order_id="o1", ge_location=(5, 1))
        state = make_state(x=5, y=1, open_orders=(order,))
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.ge_cancel_order.action_ge_cancel_order",
                   return_value=make_api_result(make_char_schema())) as mock_cancel:
            a.execute(state, client)
        assert mock_cancel.call_args.kwargs["body"].id == "o1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_actions_ge_cancel_order.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the action**

```python
# src/artifactsmmo_cli/ai/actions/ge_cancel_order.py
"""GeCancelOrderAction: cancel a posted GE order, reversing its escrow.

Cancelling frees the locked capital: a SELL order returns the escrowed item to the
inventory; a BUY order returns the escrowed gold. This is the on-need / TTL escape
that underwrites the liveness guarantee (no capital is locked forever). The exact
API return destination (inventory vs pending list) is a live-probe residual;
reconciliation (see reconcile_open_orders) corrects the predicted state from API
truth on the next cycle regardless.
"""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_ge_cancel_order_my_name_action_grandexchange_cancel_post import (
    sync as action_ge_cancel_order,
)
from artifactsmmo_api_client.models.ge_cancel_order_schema import GECancelOrderSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.open_order import OrderSide
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class GeCancelOrderAction(Action):
    """Move to the Grand Exchange and cancel a posted order, reversing its escrow."""

    tags: ClassVar[frozenset[str]] = frozenset({"npc"})

    order_id: str
    ge_location: tuple[int, int] | None = field(default=None, repr=False)

    def _order(self, state: WorldState):
        for o in state.open_orders:
            if o.id == self.order_id:
                return o
        return None

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.ge_location is None:
            return False
        return self._order(state) is not None

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        order = self._order(state)
        if order is None:
            raise AssertionError(
                f"GeCancelOrderAction.apply: order {self.order_id} not open — "
                f"is_applicable invariant violated"
            )
        new_gold = state.gold
        new_inventory = dict(state.inventory)
        if order.side is OrderSide.BUY:
            new_gold += order.price * order.qty
        else:
            new_inventory[order.code] = new_inventory.get(order.code, 0) + order.qty
        remaining = tuple(o for o in state.open_orders if o.id != self.order_id)
        dest = self.ge_location or (state.x, state.y)
        return dataclasses.replace(
            state, gold=new_gold, x=dest[0], y=dest[1],
            inventory=new_inventory, open_orders=remaining, cooldown_expires=None,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.ge_location or (state.x, state.y)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return 1.0 + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.ge_location and (state.x, state.y) != self.ge_location:
            state = MoveAction(x=self.ge_location[0], y=self.ge_location[1]).execute(state, client)
        body = GECancelOrderSchema(id=self.order_id)
        result = action_ge_cancel_order(client=client, name=state.character, body=body)
        result = Action._raise_for_error(result, f"GeCancel {self.order_id}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items, bank_gold=state.bank_gold,
            pending_items=state.pending_items, active_events=state.active_events,
            raids=state.raids,
            open_orders=tuple(o for o in state.open_orders if o.id != self.order_id),
        )

    def __repr__(self) -> str:
        return f"GeCancel({self.order_id})"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_actions_ge_cancel_order.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/ge_cancel_order.py tests/test_ai/test_actions_ge_cancel_order.py
git commit -m "feat(ge): GeCancelOrderAction reverses escrow (on-need/TTL escape)"
```

---

### Task 8: Reconciliation — settle open orders from API truth

**Files:**
- Create: `src/artifactsmmo_cli/ai/reconcile_open_orders.py`
- Modify: the per-cycle state-load path that builds `open_orders` (find the caller that reads the character's own GE orders; wire the reconcile). Search: `get_ge_orders_my_grandexchange_orders_get` usage and the cycle state builder.
- Test: `tests/test_ai/test_reconcile_open_orders.py`

**Interfaces:**
- Consumes: previous `open_orders`, the API list of currently-open orders (`(id, code, qty, price, side)` rows).
- Produces: `reconcile_open_orders(prev: tuple[OpenOrder,...], api_open: tuple[OpenOrder,...]) -> ReconcileResult` where `ReconcileResult = NamedTuple(open_orders: tuple[OpenOrder,...], filled: tuple[OpenOrder,...])`. `filled` = orders (or partial quantities) that disappeared vs `prev`; caller credits gold (SELL) / routes item to `pending_items` (BUY).

Rationale: `apply()` is optimistic prediction; this is the API-truth correction. A `prev` order absent from `api_open` (or with reduced qty) is a fill.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_reconcile_open_orders.py
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from artifactsmmo_cli.ai.reconcile_open_orders import reconcile_open_orders


def _o(id, code, qty, price, side, age=0):
    return OpenOrder(id=id, code=code, qty=qty, price=price, side=side, age=age)


def test_disappeared_order_is_a_fill():
    prev = (_o("o1", "iron_ore", 3, 19, OrderSide.SELL),)
    api_open = ()
    res = reconcile_open_orders(prev, api_open)
    assert res.open_orders == ()
    assert res.filled == (_o("o1", "iron_ore", 3, 19, OrderSide.SELL),)


def test_reduced_quantity_is_a_partial_fill():
    prev = (_o("o1", "iron_ore", 5, 19, OrderSide.SELL),)
    api_open = (_o("o1", "iron_ore", 2, 19, OrderSide.SELL),)
    res = reconcile_open_orders(prev, api_open)
    assert res.open_orders[0].qty == 2
    assert res.filled[0].qty == 3        # 5 -> 2 = 3 filled


def test_still_open_order_ages_by_one():
    prev = (_o("o1", "iron_ore", 5, 19, OrderSide.SELL, age=2),)
    api_open = (_o("o1", "iron_ore", 5, 19, OrderSide.SELL, age=0),)
    res = reconcile_open_orders(prev, api_open)
    assert res.open_orders[0].age == 3   # aged, not reset
    assert res.filled == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_reconcile_open_orders.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the reconciler**

```python
# src/artifactsmmo_cli/ai/reconcile_open_orders.py
"""Reconcile predicted open-order state against API truth each cycle.

apply() predicts posts/cancels optimistically; the API's list of the character's
currently-open orders is the source of truth. An order present last cycle but gone
(or reduced in quantity) this cycle is a FILL: the caller credits gold for a SELL
and routes the item into pending_items for a BUY. Still-open orders age by one cycle
(the TTL cancel reads that age)."""

from typing import NamedTuple

from artifactsmmo_cli.ai.open_order import OpenOrder


class ReconcileResult(NamedTuple):
    open_orders: tuple[OpenOrder, ...]
    filled: tuple[OpenOrder, ...]


def reconcile_open_orders(
    prev: tuple[OpenOrder, ...], api_open: tuple[OpenOrder, ...]
) -> ReconcileResult:
    by_id = {o.id: o for o in api_open}
    still_open: list[OpenOrder] = []
    filled: list[OpenOrder] = []
    for p in prev:
        current = by_id.get(p.id)
        if current is None:
            filled.append(p)                       # whole order filled/gone
            continue
        if current.qty < p.qty:
            filled.append(p._replace(qty=p.qty - current.qty))   # partial fill delta
        still_open.append(current._replace(age=p.age + 1))       # keep aging
    # Orders the API reports that we did not know about (e.g. restored session) pass
    # through un-aged so the planner still tracks them.
    known = {p.id for p in prev}
    for o in api_open:
        if o.id not in known:
            still_open.append(o)
    ordered = tuple(sorted(still_open, key=lambda o: (o.side.value, o.code, o.price, o.id)))
    return ReconcileResult(open_orders=ordered, filled=tuple(filled))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_reconcile_open_orders.py -v`
Expected: PASS.

- [ ] **Step 5: Wire into the cycle state-load path**

Find the per-cycle builder that constructs `WorldState` for the live loop (the code that already reads bank/pending; search for `get_ge_orders_my_grandexchange_orders_get` and the state-refresh site). Read the character's own open orders via that client fn, map each API row to `OpenOrder`, call `reconcile_open_orders(prev_state.open_orders, api_open)`, then: for each `filled` SELL add `price*qty` to gold, for each `filled` BUY append `(id, code)` to `pending_items` (so `ClaimPendingGoal` collects it), and set `open_orders=res.open_orders`. Add a focused test in `tests/test_ai/` for that wiring using the existing state-load test fixtures.

- [ ] **Step 6: Run the wiring test + type-check**

Run: `uv run pytest tests/test_ai/test_reconcile_open_orders.py -v && uv run mypy src/artifactsmmo_cli/ai/reconcile_open_orders.py`
Expected: PASS, no mypy errors.

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/reconcile_open_orders.py tests/test_ai/test_reconcile_open_orders.py
git commit -m "feat(ge): reconcile open orders from API truth (fill detection + aging)"
```

---

### Task 9: `bid_vs_craft.py` — craft-time estimate + bid gate

**Files:**
- Create: `src/artifactsmmo_cli/ai/bid_vs_craft.py`
- Test: `tests/test_ai/test_bid_vs_craft.py`

**Interfaces:**
- Consumes: `RequirementGraph.sources` (`requirement_graph.py:123`), `recipe_closure` (`recipe_closure.py:195`), `_expected_kills`/`select_monster_for_drop` (`monster_drop_selection.py`), `SourceKind` (Task 7 unchanged), `GameData`.
- Produces:
  - `closure_leaf_kinds(item: str, game_data: GameData) -> frozenset[SourceKind]`
  - `estimate_craft_seconds(item: str, qty: int, game_data: GameData) -> float`
  - `should_bid(item: str, qty: int, bid_fill_horizon_s: float, game_data: GameData) -> bool`

Gate: `should_bid` returns True iff `estimate_craft_seconds > bid_fill_horizon_s` (self-craft is the slow path) AND a live buy-anchor exists (checked by the caller via `buy_post_price`). Drop legs use the STATIC API rate via `_expected_kills` (the A* fight-leg cost is rate-blind; this estimator is not).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_bid_vs_craft.py
from artifactsmmo_cli.ai.bid_vs_craft import should_bid, estimate_craft_seconds, closure_leaf_kinds
from artifactsmmo_cli.ai.source_kind import SourceKind
# Build a GameData with a known recipe/drop graph using the existing catalog test
# fixtures (see tests/test_ai/test_requirement_graph.py for the builder pattern).
from tests.test_ai.catalog_fixtures import make_game_data_with_recipes  # existing helper


def test_closure_leaf_kinds_flags_drop_based():
    gd = make_game_data_with_recipes(
        recipes={"steel": {"iron": 2}},
        drops={"iron": [("mob", 5, 1, 1)]},   # iron drops 1-in-5 from mob
    )
    kinds = closure_leaf_kinds("steel", gd)
    assert SourceKind.DROP in kinds


def test_drop_recipe_costs_more_than_deterministic():
    gd = make_game_data_with_recipes(
        recipes={"steel": {"iron": 2}},
        drops={"iron": [("mob", 20, 1, 1)]},        # rare drop -> many fights
        gatherables={},
    )
    drop_cost = estimate_craft_seconds("steel", 1, gd)
    gd2 = make_game_data_with_recipes(
        recipes={"plank": {"wood": 2}},
        gatherables={"wood": ("tree", 1)},          # deterministic gather
        drops={},
    )
    det_cost = estimate_craft_seconds("plank", 1, gd2)
    assert drop_cost > det_cost


def test_should_bid_true_when_craft_slower_than_horizon():
    gd = make_game_data_with_recipes(
        recipes={"steel": {"iron": 2}},
        drops={"iron": [("mob", 50, 1, 1)]},        # very slow to self-craft
    )
    assert should_bid("steel", 1, bid_fill_horizon_s=30.0, game_data=gd) is True


def test_should_bid_false_when_craft_faster_than_horizon():
    gd = make_game_data_with_recipes(
        recipes={"plank": {"wood": 2}},
        gatherables={"wood": ("tree", 1)},
        drops={},
    )
    assert should_bid("plank", 1, bid_fill_horizon_s=300.0, game_data=gd) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_bid_vs_craft.py -v`
Expected: FAIL — `ModuleNotFoundError` (and note if `catalog_fixtures.make_game_data_with_recipes` doesn't exist yet — if so, add a small builder there mirroring `tests/test_ai/test_requirement_graph.py`'s GameData construction).

- [ ] **Step 3: Write the estimator**

```python
# src/artifactsmmo_cli/ai/bid_vs_craft.py
"""Bid-vs-craft decision: only post a GE buy order for an item when self-crafting
it would be SLOWER than the bid-fill horizon. A posted bid fills asynchronously, so
running a self-craft in parallel is wasted work — this gate (and the open_orders
suppression at the call site) keeps the two mutually exclusive.

Craft-time is estimated purely, in seconds, from static game data: deterministic
gather/craft legs summed directly; DROP legs valued at expected-fights × fight-cost
using the STATIC API drop rate (the A* fight-leg cost is rate-blind, so this
estimator folds the rate in itself). Refining the static rate with learned
drops-per-fight is a documented v2 (learning store carries no drop rate today).
"""

from fractions import Fraction

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.monster_drop_selection import _expected_kills
from artifactsmmo_cli.ai.recipe_closure import recipe_closure
from artifactsmmo_cli.ai.requirement_graph import build_requirement_graph
from artifactsmmo_cli.ai.source_kind import SourceKind

# Per-action second estimates aligned with the A* edge costs (combat.py / gathering.py).
_FIGHT_SECONDS = 10.0
_GATHER_SECONDS = 6.0
_CRAFT_SECONDS = 5.0


def closure_leaf_kinds(item: str, game_data: GameData) -> frozenset[SourceKind]:
    """Union of leaf SourceKinds over item's full recipe closure — does obtaining it
    ultimately require monster DROPs, or only deterministic GATHER/CRAFT?"""
    graph = build_requirement_graph((item,), game_data)
    craftable, raw = recipe_closure((item,), game_data)
    kinds: set[SourceKind] = set()
    for node in (*craftable, *raw, item):
        kinds |= set(graph.sources(node))
    return frozenset(kinds)


def estimate_craft_seconds(item: str, qty: int, game_data: GameData) -> float:
    """Pure estimate of seconds to self-produce `qty` of `item`, folding the static
    drop rate into drop legs. Deterministic legs cost their flat per-action second."""
    _craftable, raw = recipe_closure((item,), game_data)
    total = float(_CRAFT_SECONDS) * qty
    for mat in raw:
        drops = game_data.monsters_dropping(mat)
        if drops:
            best = min(_expected_kills(rate, (min_q + max_q) / 2)
                       for _mob, rate, min_q, max_q in drops)
            total += float(best) * _FIGHT_SECONDS * qty
        else:
            total += _GATHER_SECONDS * qty
    return total


def should_bid(item: str, qty: int, bid_fill_horizon_s: float, game_data: GameData) -> bool:
    """Bid only when self-crafting is slower than we are willing to wait for a fill."""
    return estimate_craft_seconds(item, qty, game_data) > bid_fill_horizon_s
```

Note: confirm `_expected_kills`'s exact signature (`monster_drop_selection.py:23`) and adapt the call — it may take `(rate, avg_quantity)` or compute `avg_quantity` internally. Read that file and match it exactly (do not guess).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_bid_vs_craft.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/bid_vs_craft.py tests/test_ai/test_bid_vs_craft.py
git commit -m "feat(ge): bid-vs-craft estimator (static drop rate, TTL horizon gate)"
```

---

### Task 10: Sell-post injection + batch sizing (extend `discard_overstock`)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/discard_overstock.py` (~121-137, alongside the existing `GeFillBuyOrderAction` injection)
- Modify: `src/artifactsmmo_cli/ai/goals/gathering.py` (~540-558) for the buy-fill vs post choice (post-buy handled fully in Task 12; here just switch to `choose_venue3`/`choose_buy_venue3`)
- Test: `tests/test_ai/test_goals_discard_overstock.py`

**Interfaces:**
- Consumes: `choose_venue3` (Task 4), `sell_post_price` (Task 2), `GePostSellOrderAction` (Task 5), `game_data.ge_best_sell_order` (for the undercut anchor + batch qty).
- Produces: a `GePostSellOrderAction` candidate offered when `choose_venue3(...) is Venue.GE_POST`, with `quantity` = the best standing sell order's qty (batch sizing), capped at the excess.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_ai/test_goals_discard_overstock.py
# Scenario: surplus of iron_ore, NO fillable buy order, but a standing SELL order
# exists to anchor a post price ABOVE the NPC floor -> expect a GePostSellOrderAction
# sized to the standing sell order's quantity.
from artifactsmmo_cli.ai.actions.ge_post_sell import GePostSellOrderAction


def test_offers_post_sell_when_post_beats_npc_and_no_fill(discard_env):
    env = discard_env(
        inventory={"iron_ore": 40}, keep={"iron_ore": 0},
        npc_sellback={"iron_ore": 5},
        ge_buy_orders={},                                   # nothing to fill
        ge_sell_orders={"iron_ore": ("s1", 20, 8)},         # anchor: best sell 20, qty 8
    )
    actions = env.goal.available_actions(env.state, env.game_data)
    posts = [a for a in actions if isinstance(a, GePostSellOrderAction)]
    assert posts, "expected a GePostSellOrderAction"
    assert posts[0].price == 19          # undercut best_sell 20 by one tick
    assert posts[0].quantity == 8        # batch = best standing sell order's qty
```

(Use the existing `discard_overstock` test harness — mirror its current fixture that builds `state`+`game_data`; if a `discard_env` helper doesn't exist, adapt the pattern already in that test file.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_goals_discard_overstock.py -k post_sell -v`
Expected: FAIL — no `GePostSellOrderAction` offered.

- [ ] **Step 3: Add the injection**

In `discard_overstock.py`, right after the existing `GeFillBuyOrderAction` block (~137), add:

```python
            # Post our own SELL order when no standing buy order is worth filling but
            # the book gives an anchor and the post price beats the NPC floor.
            # choose_venue3 -> GE_POST (proved fail-closed in GePostPricing.lean).
            sell_anchor = game_data.ge_best_sell_order(code)
            best_sell = sell_anchor[1] if sell_anchor is not None else None
            fill_proceeds = order[1] if (order is not None and order[2] >= excess_qty) else None
            post_price = sell_post_price(best_sell, npc_sellback=npc_pay, margin=1)
            if ge_loc is not None and \
                    choose_venue3(npc_pay, fill_proceeds, post_price) is Venue.GE_POST:
                # Batch to the standing sell order's size, capped at the excess.
                batch = min(excess_qty, sell_anchor[2]) if sell_anchor is not None else excess_qty
                result.append(GePostSellOrderAction(
                    item_code=code, quantity=batch, price=post_price, ge_location=ge_loc,
                ))
```

Add imports at the top of the file:

```python
from artifactsmmo_cli.ai.actions.ge_post_sell import GePostSellOrderAction
from artifactsmmo_cli.ai.ge_post_pricing import sell_post_price
from artifactsmmo_cli.ai.liquidation_venue import choose_venue3  # Venue already imported
```

(`npc_pay` is the NPC sell-back already computed for the fill branch; reuse that local. If it's named differently in that scope, use the existing local.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_goals_discard_overstock.py -v`
Expected: PASS (existing fill tests + the new post test).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/discard_overstock.py tests/test_ai/test_goals_discard_overstock.py
git commit -m "feat(ge): inject post-sell orders with best-order-size batching"
```

---

### Task 11: `MeansKind.GE_BID` + reactive buy-post goal (DecideKey/Oracle lockstep)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/means.py` (append `GE_BID` LAST; add to `DISCRETIONARY_ORDER`)
- Modify: `formal/Formal/DecideKey.lean` + the Oracle + `decide_key` mapping (lockstep — read the recycle-surplus / drain-bank-junk precedent for the exact touch-points)
- Create: `src/artifactsmmo_cli/ai/goals/post_buy_bid.py`
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (register the goal in the means map ~350-373)
- Test: `tests/test_ai/test_goals_post_buy_bid.py`, `tests/test_ai/test_decide_key_parity.py` (or the existing decide-key diff test)

**Interfaces:**
- Consumes: `should_bid` (Task 9), `buy_post_price` (Task 2), `GePostBuyOrderAction` (Task 6), `choose_buy_venue3` (Task 4), `game_data.ge_best_buy_order`.
- Produces: `PostBuyBidGoal` emitting a `GePostBuyOrderAction` for a needed material when `should_bid` and `choose_buy_venue3 is BuyVenue.GE_POST` and no open order / committed craft for that item exists (suppression).

- [ ] **Step 0: Create `ge_order_config.py` first (needed by this task's import)**

`PostBuyBidGoal` imports `BID_FILL_HORIZON_SECONDS` from `ge_order_config.py`. Create that file now (its full content is in Task 13 Step 3) before writing the goal, so the import resolves:

```python
# src/artifactsmmo_cli/ai/ge_order_config.py
TTL_CYCLES = 20
AVG_CYCLE_SECONDS = 30.0
BID_FILL_HORIZON_SECONDS = TTL_CYCLES * AVG_CYCLE_SECONDS
```

Task 13 Step 3 then adds `cancel_selection.py` alongside it (do not recreate the config there).

- [ ] **Step 1: Append the enum member (LAST) + priority slot**

In `means.py`, add to `MeansKind` after `DRAIN_BANK_JUNK`:

```python
    GE_BID = "ge_bid"  # 2026-07-24: post a discretionary GE buy order for a slow-to-craft item.
```

Insert into `DISCRETIONARY_ORDER` just above `DRAIN_BANK_JUNK` (discretionary, below consumables/sell/recycle, above pure junk-drain):

```python
    MeansKind.RECYCLE_SURPLUS,
    MeansKind.BANK_EXPAND,
    MeansKind.GE_BID,           # opportunistic cheap acquisition, below housekeeping investments
    MeansKind.DRAIN_BANK_JUNK,
    MeansKind.WAIT,
```

- [ ] **Step 2: Update DecideKey/Oracle in lockstep + run the parity test to see it fail**

Follow the exact procedure used when `RECYCLE_SURPLUS`/`DRAIN_BANK_JUNK` were added (project memory: "new MeansKind needs DecideKey.lean+Oracle+decide_key lockstep"). Read `formal/Formal/DecideKey.lean` and the Oracle mapping, add the `GE_BID` case in the same three places, keeping the enum index stable (member appended LAST).

Run: `uv run pytest tests/test_ai/ -k decide_key -v`
Expected: FAIL first (parity mismatch) until all three lockstep sites include `GE_BID`; then PASS.

- [ ] **Step 3: Write the failing goal test**

```python
# tests/test_ai/test_goals_post_buy_bid.py
from artifactsmmo_cli.ai.actions.ge_post_buy import GePostBuyOrderAction
from artifactsmmo_cli.ai.goals.post_buy_bid import PostBuyBidGoal


def test_bids_for_slow_to_craft_needed_item(bid_env):
    env = bid_env(
        needed={"steel": 1},
        drops={"iron": [("mob", 50, 1, 1)]},   # steel is slow to self-craft
        recipes={"steel": {"iron": 2}},
        npc_price={"steel": 100},
        ge_buy_orders={"steel": ("b1", 40, 5)},   # anchor to overbid
        ge_sell_orders={},                        # nothing cheap to fill
        gold=1000,
    )
    actions = PostBuyBidGoal().available_actions(env.state, env.game_data)
    bids = [a for a in actions if isinstance(a, GePostBuyOrderAction)]
    assert bids and bids[0].price == 41           # overbid best_buy 40 by one tick


def test_no_bid_when_item_already_has_open_order(bid_env):
    from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
    env = bid_env(
        needed={"steel": 1}, drops={"iron": [("mob", 50, 1, 1)]},
        recipes={"steel": {"iron": 2}}, npc_price={"steel": 100},
        ge_buy_orders={"steel": ("b1", 40, 5)}, gold=1000,
        open_orders=(OpenOrder("x", "steel", 1, 41, OrderSide.BUY, 0),),
    )
    actions = PostBuyBidGoal().available_actions(env.state, env.game_data)
    assert not [a for a in actions if isinstance(a, GePostBuyOrderAction)]  # suppressed
```

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_goals_post_buy_bid.py -v`
Expected: FAIL — `ModuleNotFoundError` for `post_buy_bid`.

- [ ] **Step 5: Write the goal**

```python
# src/artifactsmmo_cli/ai/goals/post_buy_bid.py
"""PostBuyBidGoal: post discretionary GE buy orders for items that are slow to
self-craft, so long as the bid is cheaper than the NPC/fill alternative and we are
not already acquiring the item another way.

Reactive means (not an obtain-graph source): a posted bid fills asynchronously, so
this never claims to synchronously satisfy a material need — it just replaces an
otherwise-more-expensive acquisition with a cheaper deferred one. Suppression:
skip any item that already has an open order or a committed self-craft, keeping bid
and craft mutually exclusive (bid_vs_craft)."""

from artifactsmmo_cli.ai.actions.ge_post_buy import GePostBuyOrderAction
from artifactsmmo_cli.ai.bid_vs_craft import should_bid
from artifactsmmo_cli.ai.buy_source_venue import BuyVenue, choose_buy_venue3
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.ge_post_pricing import buy_post_price
from artifactsmmo_cli.ai.world_state import WorldState

# Bid-fill horizon = TTL_CYCLES × average cycle seconds (Task 13 defines TTL_CYCLES).
from artifactsmmo_cli.ai.ge_order_config import BID_FILL_HORIZON_SECONDS


class PostBuyBidGoal:
    def available_actions(self, state: WorldState, game_data: GameData) -> list[GePostBuyOrderAction]:
        ge_loc = game_data.grand_exchange_location()
        if ge_loc is None:
            return []
        open_codes = {o.code for o in state.open_orders}
        actions: list[GePostBuyOrderAction] = []
        for item, qty in self._needed_items(state, game_data):
            if item in open_codes:
                continue                                    # suppression: already in flight
            if not should_bid(item, qty, BID_FILL_HORIZON_SECONDS, game_data):
                continue
            buy_anchor = game_data.ge_best_buy_order(item)
            best_buy = buy_anchor[1] if buy_anchor is not None else None
            npc_price = game_data.npc_buy_price(item)       # existing accessor; confirm name
            if npc_price is None:
                continue
            sell_order = game_data.ge_best_sell_order(item)
            fill_cost = sell_order[1] if sell_order is not None else None
            post_price = buy_post_price(best_buy, alt_cost=npc_price, margin=1)
            if choose_buy_venue3(npc_price, fill_cost, post_price) is BuyVenue.GE_POST:
                actions.append(GePostBuyOrderAction(
                    item_code=item, quantity=qty, price=post_price, ge_location=ge_loc,
                ))
        return actions

    def _needed_items(self, state: WorldState, game_data: GameData):
        """Materials the character will need but does not hold — reuse the existing
        objective/closure-demand source the planner already computes (see
        closure_demand / objective_needs). Return (item_code, qty) pairs."""
        raise NotImplementedError  # wire to closure_demand in Step 6
```

- [ ] **Step 6: Wire `_needed_items` to the existing demand source + register the goal**

Replace the `_needed_items` stub with a call into the existing `closure_demand` / `objective_needs` machinery the planner already uses (project memory: requirement-model unification exposes `objective_needs`/`closure_demand`). Register `PostBuyBidGoal` under `MeansKind.GE_BID` in `strategy_driver.py`'s means map (~350-373), mirroring how `RECYCLE_SURPLUS`/`SELL_IDLE` are registered.

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_goals_post_buy_bid.py tests/test_ai/ -k decide_key -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/post_buy_bid.py src/artifactsmmo_cli/ai/tiers/means.py src/artifactsmmo_cli/ai/strategy_driver.py formal/Formal/DecideKey.lean tests/test_ai/test_goals_post_buy_bid.py
git commit -m "feat(ge): GE_BID discretionary means + reactive buy-post goal (oracle lockstep)"
```

---

### Task 12: Craft/gather suppression while a bid is open

**Files:**
- Modify: the craft/gather goal(s) that emit acquisition for a needed item — `src/artifactsmmo_cli/ai/goals/gathering.py` and the craft goal — to skip items in `state.open_orders`.
- Test: `tests/test_ai/test_bid_suppression.py`

**Interfaces:**
- Consumes: `state.open_orders`.
- Produces: no new symbols — a guard `if item in {o.code for o in state.open_orders}: continue` in the acquisition emitters, so a bid and a self-craft never run for the same item.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_bid_suppression.py
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide


def test_no_gather_or_craft_for_item_with_open_buy_order(gather_env):
    order = OpenOrder("b1", "iron_ore", 5, 9, OrderSide.BUY, 0)
    env = gather_env(needed={"iron_ore": 5}, open_orders=(order,))
    actions = env.goal.available_actions(env.state, env.game_data)
    # No gather/craft action should target iron_ore while its bid is open.
    assert all(getattr(a, "item_code", None) != "iron_ore"
               and getattr(a, "resource_code", None) != "iron_ore"
               for a in actions)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_bid_suppression.py -v`
Expected: FAIL — gather/craft still offered for the bid item.

- [ ] **Step 3: Add the suppression guard**

In the acquisition emitters (the loop in `gathering.py` that builds gather/fill actions for `item`, and the corresponding craft goal loop), add near the top of the per-item body:

```python
            if item in {o.code for o in state.open_orders}:
                continue  # a GE bid is already in flight for this item (bid_vs_craft exclusion)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_bid_suppression.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/gathering.py tests/test_ai/test_bid_suppression.py
git commit -m "feat(ge): suppress craft/gather for items with an open bid"
```

---

### Task 13: Cancellation triggers — on-need guard + TTL sweep

**Files:**
- Create: `src/artifactsmmo_cli/ai/ge_order_config.py` (`TTL_CYCLES`, `AVG_CYCLE_SECONDS`, `BID_FILL_HORIZON_SECONDS = TTL_CYCLES * AVG_CYCLE_SECONDS`)
- Create: `src/artifactsmmo_cli/ai/cancel_selection.py` (pure: which open orders to cancel)
- Modify: `src/artifactsmmo_cli/ai/tiers/guards.py` (append `GuardKind.GE_CANCEL_ONNEED` LAST; slot into `GUARD_ORDER`) + DecideKey/Oracle lockstep for guards
- Create: `src/artifactsmmo_cli/ai/goals/cancel_stale_orders.py` (TTL sweep, low-priority means) — or fold into an existing housekeeping means
- Test: `tests/test_ai/test_cancel_selection.py`

**Interfaces:**
- Produces:
  - `cancel_targets(state, game_data, need_gold: int, needed_items: frozenset[str]) -> tuple[str, ...]` (order ids to cancel): a BUY order when gold is short of `need_gold` and cancelling frees enough; a SELL order whose item is in `needed_items`; any order with `age > TTL_CYCLES`.
  - `BID_FILL_HORIZON_SECONDS` (consumed by Task 11).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_cancel_selection.py
from artifactsmmo_cli.ai.cancel_selection import cancel_targets
from artifactsmmo_cli.ai.ge_order_config import TTL_CYCLES
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from tests.test_ai.fixtures import make_state


def _buy(id, code, qty, price, age=0):
    return OpenOrder(id, code, qty, price, OrderSide.BUY, age)


def _sell(id, code, qty, price, age=0):
    return OpenOrder(id, code, qty, price, OrderSide.SELL, age)


def test_cancels_buy_order_when_gold_needed(game_data):
    state = make_state(gold=5, open_orders=(_buy("b1", "iron", 3, 9, age=0),))
    ids = cancel_targets(state, game_data, need_gold=20, needed_items=frozenset())
    assert "b1" in ids                                   # frees 27 gold to reach 20

def test_cancels_sell_order_when_item_needed(game_data):
    state = make_state(open_orders=(_sell("s1", "iron", 3, 19, age=0),))
    ids = cancel_targets(state, game_data, need_gold=0, needed_items=frozenset({"iron"}))
    assert "s1" in ids

def test_cancels_stale_order_past_ttl(game_data):
    state = make_state(open_orders=(_sell("s2", "iron", 3, 19, age=TTL_CYCLES + 1),))
    ids = cancel_targets(state, game_data, need_gold=0, needed_items=frozenset())
    assert "s2" in ids

def test_keeps_fresh_unneeded_order(game_data):
    state = make_state(gold=999, open_orders=(_sell("s3", "iron", 3, 19, age=0),))
    ids = cancel_targets(state, game_data, need_gold=0, needed_items=frozenset())
    assert ids == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_cancel_selection.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the config + selection**

```python
# src/artifactsmmo_cli/ai/ge_order_config.py
"""GE order-posting tunables. TTL bounds worst-case capital lock and defines the
bid-fill horizon that bid_vs_craft races self-craft time against."""

TTL_CYCLES = 20
AVG_CYCLE_SECONDS = 30.0
BID_FILL_HORIZON_SECONDS = TTL_CYCLES * AVG_CYCLE_SECONDS
```

```python
# src/artifactsmmo_cli/ai/cancel_selection.py
"""Pure selection of open GE orders to cancel: on-need (free locked capital the bot
needs now) plus TTL (staleness backstop). Underwrites the liveness guarantee that no
posted order's capital is locked forever."""

from artifactsmmo_cli.ai.ge_order_config import TTL_CYCLES
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.open_order import OrderSide
from artifactsmmo_cli.ai.world_state import WorldState


def cancel_targets(
    state: WorldState, game_data: GameData, need_gold: int, needed_items: frozenset[str]
) -> tuple[str, ...]:
    targets: list[str] = []
    gold_short = max(0, need_gold - state.gold)
    for o in state.open_orders:
        if o.age > TTL_CYCLES:
            targets.append(o.id)
            continue
        if o.side is OrderSide.BUY and gold_short > 0:
            targets.append(o.id)
            gold_short -= o.price * o.qty
            continue
        if o.side is OrderSide.SELL and o.code in needed_items:
            targets.append(o.id)
    # Deterministic order (dedup preserved via dict.fromkeys insertion order).
    return tuple(dict.fromkeys(targets))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_cancel_selection.py -v`
Expected: PASS.

- [ ] **Step 5: Wire guard + TTL means (lockstep) and register**

Append `GuardKind.GE_CANCEL_ONNEED` LAST in `guards.py` and slot it into `GUARD_ORDER` high (after `HP_CRITICAL`/`REST_FOR_COMBAT`, before the relief guards — freeing needed capital precedes relief). Add the DecideKey/Oracle guard-lockstep case (same procedure as Task 11 Step 2, guard side). Create `CancelStaleOrdersGoal` (TTL sweep) or fold TTL cancels into a low-priority means; emit `GeCancelOrderAction(order_id=..., ge_location=...)` for each id from `cancel_targets`. Register in `strategy_driver.py`. Add a guard-side decide-key parity test run.

- [ ] **Step 6: Run the guard parity + cancel tests**

Run: `uv run pytest tests/test_ai/ -k "cancel or decide_key or guard" -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/ge_order_config.py src/artifactsmmo_cli/ai/cancel_selection.py src/artifactsmmo_cli/ai/goals/cancel_stale_orders.py src/artifactsmmo_cli/ai/tiers/guards.py src/artifactsmmo_cli/ai/strategy_driver.py formal/Formal/DecideKey.lean tests/test_ai/test_cancel_selection.py
git commit -m "feat(ge): on-need + TTL cancellation (guard + sweep, oracle lockstep)"
```

---

### Task 14: Escrow-conservation + liveness proofs (formal-development)

**Files:**
- Create: `formal/Formal/EscrowConservation.lean`
- Modify: `formal/Formal.lean` (import)
- Test: `lake build`

**Interfaces:**
- Produces: a Lean model of the escrow lifecycle (post → fill | cancel) with conservation + liveness theorems. This is the honest formal contract for §7 of the spec; use lean4:autoprove / formal-development to discharge.

Model orders as `(qty, price, side)` and define `postSell`, `postBuy`, `fillSell`, `fillBuy`, `cancel` as pure transitions over an abstract `(gold, item_count, escrowed)` triple.

- [ ] **Step 1: Write the definitions + theorem statements**

```lean
-- formal/Formal/EscrowConservation.lean
-- @concept: grandexchange @property: conservation, liveness
import Mathlib.Data.Int.Order.Basic

namespace Formal.EscrowConservation

structure Ledger where
  gold : Int
  items : Int          -- units of the item in the bag
  escrowGold : Int     -- gold locked by open BUY orders
  escrowItems : Int    -- items locked by open SELL orders
  deriving Repr, DecidableEq

def postSell (l : Ledger) (qty price : Int) : Ledger :=
  { l with items := l.items - qty, escrowItems := l.escrowItems + qty }

def postBuy (l : Ledger) (qty price : Int) : Ledger :=
  { l with gold := l.gold - qty * price, escrowGold := l.escrowGold + qty * price }

def cancelSell (l : Ledger) (qty : Int) : Ledger :=
  { l with items := l.items + qty, escrowItems := l.escrowItems - qty }

def cancelBuy (l : Ledger) (qty price : Int) : Ledger :=
  { l with gold := l.gold + qty * price, escrowGold := l.escrowGold - qty * price }

def fillSell (l : Ledger) (qty price : Int) : Ledger :=
  { l with gold := l.gold + qty * price, escrowItems := l.escrowItems - qty }

def fillBuy (l : Ledger) (qty price : Int) : Ledger :=
  -- The escrowed gold is paid to the seller (leaves escrow); the item arrives
  -- (via the pending list in the real system, modeled here as items += qty).
  { l with items := l.items + qty, escrowGold := l.escrowGold - qty * price }

/-- CONSERVATION: post-then-cancel a SELL restores the item ledger exactly. -/
theorem sell_post_cancel_restores (l : Ledger) (qty price : Int) :
    cancelSell (postSell l qty price) qty = l := by
  simp [postSell, cancelSell]

/-- CONSERVATION: post-then-cancel a BUY restores the gold ledger exactly. -/
theorem buy_post_cancel_restores (l : Ledger) (qty price : Int) :
    cancelBuy (postBuy l qty price) qty price = l := by
  simp [postBuy, cancelBuy]

/-- CONSERVATION (sell fill): a filled SELL yields exactly qty*price gold and frees
the escrowed items — no capital minted or destroyed across post→fill. -/
theorem sell_post_fill_gold (l : Ledger) (qty price : Int) :
    (fillSell (postSell l qty price) qty price).gold = l.gold + qty * price := by
  simp [postSell, fillSell]

/-- CONSERVATION (buy fill): a filled BUY frees exactly the escrowed gold and yields
the item — no capital minted or destroyed across post→fill. -/
theorem buy_post_fill_escrow (l : Ledger) (qty price : Int) :
    (fillBuy (postBuy l qty price) qty price).escrowGold = l.escrowGold := by
  simp [postBuy, fillBuy]

/-- LIVENESS: every posted order has an escape (cancel) that frees its locked
capital, so no capital is locked forever (paired with the TTL age bound in Python). -/
theorem sell_escrow_freed (l : Ledger) (qty price : Int) :
    (cancelSell (postSell l qty price) qty).escrowItems = l.escrowItems := by
  simp [postSell, cancelSell]

theorem buy_escrow_freed (l : Ledger) (qty price : Int) :
    (cancelBuy (postBuy l qty price) qty price).escrowGold = l.escrowGold := by
  simp [postBuy, cancelBuy]

end Formal.EscrowConservation
```

- [ ] **Step 2: Add import + build**

Add `import Formal.EscrowConservation` to `formal/Formal.lean`.
Run: `cd formal && lake build 2>&1 | tail -20`
Expected: PASS (these are `simp`-provable; if a goal sticks, use lean4:prove). No sorries.

- [ ] **Step 3: Verify no sorries**

Run: `cd formal && grep -rn "sorry" Formal/EscrowConservation.lean || echo "no sorries"`
Expected: "no sorries".

- [ ] **Step 4: Commit**

```bash
git add formal/Formal/EscrowConservation.lean formal/Formal.lean
git commit -m "feat(ge): escrow conservation + liveness proofs"
```

---

### Task 15: Differential/mutation gate + coverage + runtime activation

**Files:**
- Modify: the differential harness registration for the new pure functions (`sell_post_price`/`buy_post_price`/`choose_venue3`/`choose_buy_venue3`) — mirror how `liquidation_venue`/`buy_source_venue` are registered in `formal/diff/`.
- Test: full suite + gate + live `plan`.

**Interfaces:** none new — this task verifies the whole feature.

- [ ] **Step 1: Register the new deciders in the differential gate**

Find the diff harness that pins Python `choose_venue`/`choose_buy_venue` against their Lean mirrors (`formal/diff/`). Add entries for `sell_post_price`↔`sellPostPrice`, `buy_post_price`↔`buyPostPrice`, and the 3-way `choose_venue3`↔`chooseVenue3` / `choose_buy_venue3`↔`chooseBuyVenue3`, following the existing entry format exactly.

- [ ] **Step 2: Run the formal gate**

Run: `cd formal && lake build && cd .. && uv run python formal/diff/run_diff.py`  (use the repo's actual gate entrypoint — check `scripts/` / `formal-gate.yml` for the exact command)
Expected: differential parity PASS for all new deciders.

- [ ] **Step 3: Run mutation on the new modules**

Run the mutation harness scoped to the new files (`ge_post_pricing.py`, `liquidation_venue.py`, `buy_source_venue.py`, `cancel_selection.py`, `reconcile_open_orders.py`, `bid_vs_craft.py`) per the repo's mutation runner. Serialize — never run the gate concurrently with anything importing `src` (project memory).
Expected: 0 surviving mutants (each mutation killed by a test).

- [ ] **Step 4: Full suite + coverage**

Run: `uv run bash scripts/run_tests.sh` (the parallel 2-lane runner) then a coverage check on the new files.
Expected: 0 errors, 0 warnings, 0 skipped, 100% coverage on the new modules.

- [ ] **Step 5: Runtime activation (green ≠ active)**

Run a live `plan <char>` on a character with surplus inventory and a slow-to-craft need, and confirm from the plan/log output that a `GePostSell`/`GePostBuy` candidate actually FIRES (per project memory: venue/goal changes must be verified on the live planner, not just in tests). Capture the deciding line.
Expected: a post action appears in the live plan tree for the expected item.

- [ ] **Step 6: Resolve live-probe residuals**

On the first live post/cancel, confirm and record: (1) no unexpected GE tax/fee vs `qty*price`; (2) cancel return destination (inventory vs pending) — adjust `GeCancelOrderAction.apply` only if the probe contradicts the modeled inventory-return; (3) max open-orders per account; (4) tick = 1. File any correction as a follow-up commit.

- [ ] **Step 7: Commit**

```bash
git add formal/diff/ docs/
git commit -m "test(ge): differential+mutation gate for post deciders; runtime-verified"
```

---

## Self-Review

**Spec coverage:**
- §1 order-state model → Task 1. §2 reconciliation → Task 8. §3 pricing → Tasks 2–3.
  §4 3-way venue + reactive buy trigger → Tasks 4, 10, 11. §5 actions → Tasks 5–7;
  bid-vs-craft → Task 9; suppression → Task 12. §6 triggers/cancel → Tasks 10, 11, 13.
  §7 formal contract → Tasks 3, 4, 14, 15; live-probe residuals → Task 15 Step 6. All covered.

**Placeholder scan:** Two deliberately-deferred integration points are described as
procedures rather than literal diffs — the DecideKey/Oracle lockstep (Task 11 Step 2,
Task 13 Step 5) and the demand-source wiring (Task 11 Step 6) — because they must follow
the repo's existing add-a-MeansKind procedure and existing `closure_demand` API exactly;
each names the precedent to copy and the parity test that proves it correct. The
`_expected_kills` call (Task 9 Step 3) is flagged to match the real signature. These are
integration instructions, not vague "add error handling" placeholders.

**Type consistency:** `OpenOrder`/`OrderSide` field names (`id, code, qty, price, side, age`)
are used identically across Tasks 1, 5–8, 12, 13. `choose_venue3`/`choose_buy_venue3`
signatures match between Task 4 (definition) and Tasks 10–11 (consumption).
`BID_FILL_HORIZON_SECONDS` is defined in Task 13 and consumed in Task 11 (note: Task 11
imports it before Task 13 creates it — implementers running strictly in order should create
`ge_order_config.py` as the first step of Task 11, or reorder Task 13's config split before
Task 11; called out here so the import is not a surprise).

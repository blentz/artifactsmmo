# Fleet Currency Turn-In Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the fleet notice that the artifacts its characters are *wearing* are also the currency for a better artifact, and turn them in — without ever forbidding a character from equipping one.

**Architecture:** Three new pieces and no changes to the ranking pivot. (1) A pure predicate recognises a **dual-role item**: equippable AND named as the `currency` of some NPC purchase. (2) Each `play --all` child publishes its dual-role holdings (worn + carried) to the shared coordination DB every cycle, so any child can compute a fleet total = own + siblings + bank. (3) When that total reaches a purchase price, one buyer is elected by claim, publishes a recall, siblings unequip and deposit, and the buyer withdraws and buys. Wearing the currency stays the fleet's storage mechanism; the turn-in is what harvests it.

**Tech Stack:** Python 3.13, `uv`, SQLModel/SQLite (coordination DB), pytest. Lean 4 only for the one liveness rung in Task 9.

**Spec:** This document. The measurements it argues from are in "Evidence" below; they were taken live on 2026-08-16 against `Robby` and the account's real bank.

## Evidence this plan is built on

Measured with the real planner against live state, not inferred:

- `lich_race_medal` costs 100 `event_ticket` at `archaeologist`; `lich_race_trophy` costs **10 `lich_race_medal`**. Both are `type: artifact`, so both are equippable *and* spendable.
- The strategy never selects the trophy root at any stock level. With 10 medals banked its `acquire_cost` falls to **14 actions** and `chosen_root` is still `ReachCharLevel(level=30)`, because `J` ranks by furthest reachable level first and every candidate — trunk included — ties at 30. Cost is only the tie-breaker, and the trunk's 0 wins.
- Handed the goal directly, the planner **can** buy the trophy when 10 medals are already banked (`Withdraw(lich_race_medal×10) -> NpcBuy(lich_race_trophy×1@archaeologist)`), and **cannot** accumulate them: a demand of 2 medals emits one batched `NpcBuy` needing 200 tickets against a 152-quantity bag, so `NO PLAN` at every size above ×1.
- Live fleet right now: 2 medals worn (`R2D2`, `HAL`), 142 tickets banked, 42 carried. Five characters × 3 artifact slots = 15 medal slots, so the fleet can hold more than the 10 a trophy needs.

**Consequence for the design:** the turn-in must fire from a band that does not depend on `J` choosing gear. It fires in `COLLECT_REWARD_ORDER`, above the objective step, exactly like `SUPPLY_BANK`.

## Global Constraints

- Python 3.13. Every command runs under `uv run` (`uv run pytest`, `uv run mypy`).
- **One behavioural class per file.** Two goals means two files. Pure-data/enum modules may share a file.
- No inline imports; no `if TYPE_CHECKING`; never `except Exception`.
- Use only API data or fail with an error — no defaulting around missing game data.
- Tests live in `tests/`. Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- The full gate is one command: `bash formal/gate.sh`. Redirect it to a file and check `$?` directly — a pipeline hides the real exit code.
- Mutation anchors must be refreshed in the SAME commit as the code they point at; `uv run python formal/diff/mutate.py --check-anchors` must stay green.
- Pre-commit runs `pytest tests/test_ai/` only. Anything under `tests/test_multi/` or `tests/test_utils/` must additionally be run by hand before committing.

## Non-goals

- **Not** fixing the `J` branch pivot. Every candidate tying at reach 30 is a real and separate defect; this plan routes around it rather than touching a proven core.
- **Not** preventing a character from equipping a dual-role item. Wearing them IS the storage. Task 7 only reserves the specific units an *in-flight* turn-in has already recalled, so the fleet cannot re-wear what it is mid-way through spending.
- **Not** teaching the planner repeated purchase-and-bank. One medal per plan stays the acquisition rate; this plan harvests what that rate accumulates.

## File Structure

| File | Responsibility |
|---|---|
| `src/artifactsmmo_cli/ai/dual_role_currency.py` (new) | Pure: is a code both equippable and a purchase currency; which purchases a currency unlocks. |
| `src/artifactsmmo_cli/ai/location_catalog.py` (modify) | Reverse index `currency -> [(item, npc, price)]`, built once with the other NPC maps. |
| `src/artifactsmmo_cli/ai/currency_turnin.py` (new) | Pure: fleet total, readiness verdict, recall split (who gives up how many). |
| `src/artifactsmmo_cli/ai/learning/models.py` (modify) | `HoldingLedger` + `TurnInClaim` tables. |
| `src/artifactsmmo_cli/ai/learning/coordination_store.py` (modify) | `publish_holdings` / `sibling_holdings` / `claim_turn_in` / `turn_in_claim`. |
| `src/artifactsmmo_cli/ai/selection_context.py` (modify) | Carry `fleet_holdings` and `turn_in` onto the per-cycle context. |
| `src/artifactsmmo_cli/ai/player.py` (modify) | Publish holdings each cycle; resolve the turn-in; thread both onto the context. |
| `src/artifactsmmo_cli/ai/tiers/means.py` (modify) | `MeansKind.CURRENCY_TURNIN` + its `_fires` predicate + `COLLECT_REWARD_ORDER` slot. |
| `src/artifactsmmo_cli/ai/goals/currency_turnin.py` (new) | Buyer side: withdraw the currency, buy the upgrade. |
| `src/artifactsmmo_cli/ai/goals/surrender_currency.py` (new) | Holder side: unequip and deposit the recalled units. |
| `src/artifactsmmo_cli/ai/strategy_driver.py` (modify) | Map the new means to whichever of those two goals this character is; also reserves `ctx.turn_in`'s currency code at the `empty_slot_rank_fills` call site so a surrendered unit is not immediately re-equipped (as built — see Task 7). |
| `src/artifactsmmo_cli/ai/cycle_snapshot.py` (modify) | Trace fields: fleet total, threshold, elected buyer. |
| `formal/Formal/Liveness/MeansFiring.lean` (modify) | The rung the new means owes the ladder. |

---

### Task 1: Recognise a dual-role item

**Files:**
- Create: `src/artifactsmmo_cli/ai/dual_role_currency.py`
- Modify: `src/artifactsmmo_cli/ai/location_catalog.py` (add `currency_sinks`, populate in `_build_maps`)
- Test: `tests/test_ai/test_dual_role_currency.py`

**Interfaces:**
- Consumes: `GameData.item_stats(code).type_`, `GameData.npc_purchases(item_code) -> list[tuple[str, int, str]]` (npc, price, currency), `actions.equip.ITEM_TYPE_TO_SLOTS`.
- Produces:
  - `LocationCatalog.currency_sinks(currency_code) -> list[tuple[str, str, int]]` — `(item_code, npc_code, price)`, cheapest price first.
  - `dual_role_currency.is_dual_role(code, game_data) -> bool`
  - `dual_role_currency.dual_role_holdings(state, game_data) -> dict[str, int]` — worn + carried, per dual-role code.

- [ ] **Step 1: Write the failing test**

```python
"""A dual-role item is one the character can WEAR and also SPEND."""
from artifactsmmo_cli.ai.dual_role_currency import dual_role_holdings, is_dual_role
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_dual_role_fixtures import medal_game_data  # Step 3 creates this


def test_medal_is_dual_role_because_it_is_worn_and_spent():
    gd = medal_game_data()
    assert is_dual_role("lich_race_medal", gd) is True


def test_ticket_is_not_dual_role_because_it_cannot_be_worn():
    gd = medal_game_data()
    assert is_dual_role("event_ticket", gd) is False


def test_plain_artifact_is_not_dual_role_because_nothing_takes_it_as_payment():
    gd = medal_game_data()
    assert is_dual_role("novice_guide", gd) is False


def test_holdings_count_worn_and_carried_together():
    gd = medal_game_data()
    state = make_state(inventory={"lich_race_medal": 2, "event_ticket": 30},
                       equipment={"artifact1_slot": "lich_race_medal",
                                  "artifact2_slot": "novice_guide"})
    assert dual_role_holdings(state, gd) == {"lich_race_medal": 3}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_dual_role_currency.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.dual_role_currency'`

- [ ] **Step 3: Write the fixture module**

Create `tests/test_ai/test_dual_role_fixtures.py`:

```python
"""Game data for the lich-race currency chain, shared by the turn-in tests."""
from artifactsmmo_cli.ai.game_data import GameData, ItemStats


def medal_game_data() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "lich_race_medal": ItemStats(code="lich_race_medal", level=10, type_="artifact"),
        "lich_race_trophy": ItemStats(code="lich_race_trophy", level=20, type_="artifact"),
        "novice_guide": ItemStats(code="novice_guide", level=10, type_="artifact"),
        "event_ticket": ItemStats(code="event_ticket", level=1, type_="currency"),
    }
    gd._catalog.npc_buy_currency = {
        "archaeologist": {"lich_race_medal": "event_ticket",
                          "lich_race_trophy": "lich_race_medal"},
    }
    gd._catalog.npc_buy_price = {
        "archaeologist": {"lich_race_medal": 100, "lich_race_trophy": 10},
    }
    return gd
```

Check the real attribute names on `LocationCatalog` before writing this file (`npc_buy_currency` is confirmed; the price map may be named differently) and use the real ones — the fixture must build a catalog the production reader accepts, not a lookalike.

- [ ] **Step 4: Implement `currency_sinks` on the catalog**

In `location_catalog.py`, beside `npc_purchases`:

```python
    def currency_sinks(self, currency_code: str) -> list[tuple[str, str, int]]:
        """Every purchase payable in `currency_code`, as (item, npc, price),
        cheapest first.

        The reverse of `npc_purchase_currency`. Built by walking the same
        `npc_buy_currency` map rather than a second index, so a currency that
        stops being accepted disappears from both directions at once."""
        out: list[tuple[str, str, int]] = []
        for npc_code, by_item in self.npc_buy_currency.items():
            for item_code, currency in by_item.items():
                if currency == currency_code:
                    out.append((item_code, npc_code,
                                self.npc_buy_price.get(npc_code, {}).get(item_code, 0)))
        return sorted(out, key=lambda row: (row[2], row[0]))
```

Sorting by `(price, item_code)` is a display order over equally-valid rows, not a decision tiebreak — the caller in Task 4 selects by its own predicate, never by this order.

- [ ] **Step 5: Implement the pure module**

Create `src/artifactsmmo_cli/ai/dual_role_currency.py`:

```python
"""Items that are BOTH wearable and spendable.

`lich_race_medal` is the live case: `type: artifact`, so `pick_loadout` will
wear it, and the `currency` of `lich_race_trophy`, so the archaeologist will
take it as payment. The fleet therefore stores its trophy fund in its own
artifact slots without anyone deciding to.

Nothing here forbids wearing one. Recognising the dual role is what lets the
fleet COUNT what it is wearing; `currency_turnin` decides when to spend it."""

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


def is_dual_role(code: str, game_data: GameData) -> bool:
    """True when `code` can be equipped AND is accepted as payment somewhere."""
    stats = game_data.item_stats(code)
    if stats is None or stats.type_ not in ITEM_TYPE_TO_SLOTS:
        return False
    return bool(game_data.currency_sinks(code))


def dual_role_holdings(state: WorldState, game_data: GameData) -> dict[str, int]:
    """This character's dual-role units, WORN PLUS CARRIED, per code.

    Worn units count because they are recoverable in one `UnequipAction`, and
    the whole point of the fleet ledger is that a worn medal is still fleet
    currency. The bank is deliberately absent: it is account-shared, so every
    child reads it directly and adding it here would count it once per child."""
    held: dict[str, int] = {}
    for code, qty in state.inventory.items():
        if qty > 0 and is_dual_role(code, game_data):
            held[code] = held.get(code, 0) + qty
    for code in state.equipment.values():
        if code and is_dual_role(code, game_data):
            held[code] = held.get(code, 0) + 1
    return held
```

Add the `GameData.currency_sinks` delegation next to the existing `npc_purchases` delegation, matching that method's shape exactly.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_dual_role_currency.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/dual_role_currency.py \
        src/artifactsmmo_cli/ai/location_catalog.py \
        src/artifactsmmo_cli/ai/game_data.py \
        tests/test_ai/test_dual_role_currency.py \
        tests/test_ai/test_dual_role_fixtures.py
git commit -m "feat(ai): recognise items that are both wearable and spendable"
```

---

### Task 2: Fleet holdings ledger in the coordination DB

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/models.py`
- Modify: `src/artifactsmmo_cli/ai/learning/coordination_store.py`
- Test: `tests/test_ai/test_coordination_store.py`

**Interfaces:**
- Consumes: the `expires_at` liveness rule and TTL helpers already used by `MaterialDemand`.
- Produces:
  - `CoordinationStore.publish_holdings(holdings: Mapping[str, int], now: datetime) -> None`
  - `CoordinationStore.sibling_holdings(now: datetime) -> dict[str, int]` — summed across every *other* live character.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ai/test_coordination_store.py`:

```python
def test_sibling_holdings_sums_other_characters_only(tmp_path):
    """A character's own row is excluded: the caller adds its own holdings from
    live state, which is fresher than anything it published."""
    now = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    r2d2 = CoordinationStore(db_path=db, character="R2D2")
    hal.publish_holdings({"lich_race_medal": 1}, now)
    r2d2.publish_holdings({"lich_race_medal": 2, "novice_guide": 1}, now)

    assert hal.sibling_holdings(now) == {"lich_race_medal": 2, "novice_guide": 1}
    assert r2d2.sibling_holdings(now) == {"lich_race_medal": 1}


def test_expired_holdings_stop_counting(tmp_path):
    """A dead child's medals must leave the fleet total on the same clock that
    frees its role — otherwise the turn-in threshold is met by a ghost."""
    now = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    CoordinationStore(db_path=db, character="R2D2").publish_holdings(
        {"lich_race_medal": 2}, now)

    assert hal.sibling_holdings(now) == {"lich_race_medal": 2}
    assert hal.sibling_holdings(now + timedelta(seconds=DEMAND_TTL_SECONDS + 1)) == {}


def test_publishing_replaces_rather_than_merges(tmp_path):
    """Holdings are a snapshot. A medal spent must vanish from the fleet total
    immediately, not linger until its TTL."""
    now = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    other = CoordinationStore(db_path=db, character="R2D2")
    other.publish_holdings({"lich_race_medal": 3}, now)
    other.publish_holdings({"lich_race_medal": 1}, now)

    assert hal.sibling_holdings(now) == {"lich_race_medal": 1}
```

Import `DEMAND_TTL_SECONDS` from wherever `coordination_store` defines its demand TTL; if the constant is private, add the holdings TTL as a public module constant and use that.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_coordination_store.py -k holdings -v`
Expected: FAIL — `AttributeError: 'CoordinationStore' object has no attribute 'publish_holdings'`

- [ ] **Step 3: Add the table**

In `models.py`, beside `MaterialDemand`:

```python
class HoldingLedger(SQLModel, table=True):
    """One character's holding of one DUAL-ROLE item — worn plus carried.

    Upsert key is (character, item_code), replaced wholesale like
    `MaterialDemand`, because holdings are a snapshot of right now and a spent
    unit must stop counting toward a fleet threshold at once.

    Only dual-role codes are published (`ai/dual_role_currency`), so this table
    stays a handful of rows per character rather than a mirror of five
    inventories. The bank is NOT published: it is account-shared, so every
    child would publish the same units and the fleet total would multiply by
    the number of children.

    Carries the same `expires_at` liveness rule as `RoleLease`,
    `MaterialDemand`, `BankStockClaim` and `GeOrderClaim` — a row is real if
    unexpired — so the coordination system still has exactly ONE liveness
    rule."""

    __tablename__ = "holding_ledger"
    __table_args__ = (
        UniqueConstraint("character", "item_code", name="uq_holding_ledger_holder"),
    )

    id: int | None = Field(default=None, primary_key=True)
    character: str = Field(index=True)
    item_code: str = Field(index=True)
    quantity: int
    expires_at: str
```

- [ ] **Step 4: Add the store methods**

In `coordination_store.py`, modelled line-for-line on `publish_demand` / `sibling_demand`: delete this character's rows, insert the non-zero ones with `self._demand_expiry(now)`, and sum unexpired rows from other characters in `sibling_holdings`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_coordination_store.py -v`
Expected: PASS, including the three new tests.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/models.py \
        src/artifactsmmo_cli/ai/learning/coordination_store.py \
        tests/test_ai/test_coordination_store.py
git commit -m "feat(coordination): publish per-character dual-role holdings"
```

---

### Task 3: The readiness core

**Files:**
- Create: `src/artifactsmmo_cli/ai/currency_turnin.py`
- Test: `tests/test_ai/test_currency_turnin.py`

**Interfaces:**
- Consumes: nothing but plain data — this module is pure so the decision can be tested without a fleet.
- Produces:
  - `TurnIn` dataclass: `item_code: str`, `npc_code: str`, `price: int`, `currency: str`, `buyer: str`, `fleet_total: int`
  - `fleet_total_pure(own: Mapping[str, int], siblings: Mapping[str, int], bank: Mapping[str, int], code: str) -> int`
  - `turn_in_ready_pure(fleet_total: int, price: int) -> bool`
  - `recall_shortfall_pure(price: int, buyer_held: int, bank: int) -> int` — units the buyer still needs siblings to surrender.

- [ ] **Step 1: Write the failing test**

```python
"""When does the fleet have enough of a currency to buy the upgrade?"""
import pytest

from artifactsmmo_cli.ai.currency_turnin import (
    fleet_total_pure,
    recall_shortfall_pure,
    turn_in_ready_pure,
)


def test_fleet_total_adds_own_siblings_and_bank():
    assert fleet_total_pure({"m": 3}, {"m": 5}, {"m": 2}, "m") == 10


def test_fleet_total_is_zero_for_an_unheld_code():
    assert fleet_total_pure({"m": 3}, {"m": 5}, {"m": 2}, "other") == 0


@pytest.mark.parametrize("total,ready", [(9, False), (10, True), (11, True)])
def test_readiness_is_at_or_above_the_price(total, ready):
    assert turn_in_ready_pure(total, price=10) is ready


def test_readiness_is_false_for_a_priceless_item():
    """A zero price means the catalog never gave us one; buying on that would
    be inventing game data."""
    assert turn_in_ready_pure(10, price=0) is False


def test_shortfall_counts_only_what_the_buyer_cannot_reach_alone():
    # Buyer wears 2, bank holds 3, price is 10 -> siblings must surrender 5.
    assert recall_shortfall_pure(price=10, buyer_held=2, bank=3) == 5


def test_shortfall_is_zero_when_the_buyer_and_bank_already_cover_it():
    assert recall_shortfall_pure(price=10, buyer_held=4, bank=9) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_currency_turnin.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.currency_turnin'`

- [ ] **Step 3: Implement**

```python
"""When the fleet's dual-role stock is enough to buy the thing it pays for.

Pure over plain mappings so the whole decision is testable without a
coordination DB, five characters, or a live account.

THE THRESHOLD IS THE VENDOR'S PRICE, NOT A TUNED CONSTANT. `lich_race_trophy`
costs exactly 10 `lich_race_medal`; asking for a margin on top would be a
number nobody could derive from the game."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class TurnIn:
    """A resolved turn-in: what to buy, where, in what currency, by whom."""

    item_code: str
    npc_code: str
    price: int
    currency: str
    buyer: str
    fleet_total: int


def fleet_total_pure(own: Mapping[str, int], siblings: Mapping[str, int],
                     bank: Mapping[str, int], code: str) -> int:
    """Units of `code` the whole account can reach: this character's worn and
    carried units, every live sibling's, and the shared bank.

    The bank is added exactly once because only one of the three arguments is
    allowed to carry it — see `HoldingLedger`, which never publishes it."""
    return own.get(code, 0) + siblings.get(code, 0) + bank.get(code, 0)


def turn_in_ready_pure(fleet_total: int, price: int) -> bool:
    """True when the fleet can pay the vendor's price outright."""
    if price <= 0:
        return False
    return fleet_total >= price


def recall_shortfall_pure(price: int, buyer_held: int, bank: int) -> int:
    """Units the buyer must ask siblings to surrender, never negative.

    The buyer's own worn/carried units and the bank are reachable without any
    coordination, so only the remainder is a recall."""
    return max(0, price - buyer_held - bank)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_currency_turnin.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/currency_turnin.py tests/test_ai/test_currency_turnin.py
git commit -m "feat(ai): pure core for fleet currency turn-in readiness"
```

---

### Task 4: Elect exactly one buyer

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/models.py` (add `TurnInClaim`)
- Modify: `src/artifactsmmo_cli/ai/learning/coordination_store.py`
- Test: `tests/test_ai/test_coordination_store.py`

**Interfaces:**
- Consumes: `HoldingLedger` TTL helpers from Task 2.
- Produces:
  - `CoordinationStore.claim_turn_in(item_code: str, now: datetime) -> bool` — True iff this character now holds the claim.
  - `CoordinationStore.turn_in_holder(item_code: str, now: datetime) -> str | None`
  - `CoordinationStore.release_turn_in(item_code: str) -> None`

The claim is what stops five children each recalling the same medals. Model it on `RoleLease.claim` (which already returns a win/lose boolean under a unique index) rather than on `GeOrderClaim` (which accumulates and never contends).

- [ ] **Step 1: Write the failing test**

```python
def test_only_one_character_wins_the_turn_in_claim(tmp_path):
    now = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    r2d2 = CoordinationStore(db_path=db, character="R2D2")

    assert hal.claim_turn_in("lich_race_trophy", now) is True
    assert r2d2.claim_turn_in("lich_race_trophy", now) is False
    assert hal.turn_in_holder("lich_race_trophy", now) == "HAL"
    assert r2d2.turn_in_holder("lich_race_trophy", now) == "HAL"


def test_a_released_claim_can_be_taken_by_a_sibling(tmp_path):
    now = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    r2d2 = CoordinationStore(db_path=db, character="R2D2")
    hal.claim_turn_in("lich_race_trophy", now)
    hal.release_turn_in("lich_race_trophy")

    assert r2d2.claim_turn_in("lich_race_trophy", now) is True


def test_an_expired_claim_does_not_strand_the_turn_in(tmp_path):
    """A child that dies mid-turn-in must not hold the trophy hostage."""
    now = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    db = str(tmp_path / "coord.db")
    CoordinationStore(db_path=db, character="HAL").claim_turn_in("lich_race_trophy", now)
    later = now + timedelta(seconds=DEMAND_TTL_SECONDS + 1)

    assert CoordinationStore(db_path=db, character="R2D2").claim_turn_in(
        "lich_race_trophy", later) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_coordination_store.py -k turn_in -v`
Expected: FAIL — `AttributeError: 'CoordinationStore' object has no attribute 'claim_turn_in'`

- [ ] **Step 3: Implement the table and the three methods**

`TurnInClaim` columns: `id`, `item_code` (indexed), `character` (indexed), `claimed_at`, `expires_at`, with `UniqueConstraint("item_code", name="uq_turn_in_claim_item")` — the uniqueness is on the ITEM, which is what makes the claim exclusive. Reuse `RoleLease.claim`'s insert-and-catch-integrity-error shape, including its handling of an expired incumbent row.

`claim_turn_in` renews in place when this character already holds it, so a multi-cycle turn-in does not lose its own claim.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_coordination_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/models.py \
        src/artifactsmmo_cli/ai/learning/coordination_store.py \
        tests/test_ai/test_coordination_store.py
git commit -m "feat(coordination): exclusive claim on a fleet turn-in"
```

---

### Task 5: Resolve the turn-in once per cycle in the player

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (`_update_coordination`, `_selection_context`)
- Modify: `src/artifactsmmo_cli/ai/selection_context.py`
- Test: `tests/test_ai/test_player_turn_in.py`

**Interfaces:**
- Consumes: `dual_role_holdings` (Task 1), `publish_holdings`/`sibling_holdings` (Task 2), `fleet_total_pure`/`turn_in_ready_pure`/`TurnIn` (Task 3), `claim_turn_in`/`turn_in_holder` (Task 4).
- Produces:
  - `SelectionContext.turn_in: TurnIn | None` — set on every character, buyer and holder alike.
  - `SelectionContext.recall: tuple[str, int] | None` — `(currency_code, units_this_character_should_surrender)`, None for the buyer.
  - `GamePlayer._resolve_turn_in(state, game_data) -> None`

Resolution rules, all of them checkable:
1. For each dual-role code the fleet holds, take every `currency_sinks(code)` row.
2. Ready iff `turn_in_ready_pure(fleet_total, price)`.
3. Buying must be an upgrade: `pick_loadout_cached(Rank(), state_holding_the_item, game_data)` must place `item_code` in a slot. If the picker would not wear it, do not spend the fleet's currency on it.
4. The buyer must satisfy the item's level requirement (`item_stats(item_code).level <= state.level`); a character that cannot wear it must not win the claim.
5. Exactly one candidate is pursued per cycle — if several qualify, take the one whose `price` is highest, since a bigger sink consumes stock the smaller one would fragment.

- [ ] **Step 1: Write the failing test**

```python
"""The fleet notices it is WEARING the trophy's price."""
from dataclasses import replace

from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_dual_role_fixtures import medal_game_data


def _player_with(tmp_path, name):
    store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character=name)
    player = GamePlayer(character=name)
    player._coordination = store
    player.game_data = medal_game_data()
    return player, store


def test_turn_in_resolves_when_the_fleet_wears_enough(tmp_path):
    player, store = _player_with(tmp_path, "Robby")
    for sibling, worn in (("HAL", 3), ("R2D2", 3), ("C3P0", 2)):
        CoordinationStore(db_path=str(tmp_path / "coord.db"),
                          character=sibling).publish_holdings(
                              {"lich_race_medal": worn}, NOW)
    state = make_state(level=27, inventory={}, bank_items={"lich_race_medal": 1},
                       equipment={"artifact1_slot": "lich_race_medal"})

    player._resolve_turn_in(state, player.game_data)
    turn_in = player._turn_in

    assert turn_in is not None
    assert turn_in.item_code == "lich_race_trophy"
    assert turn_in.price == 10
    assert turn_in.currency == "lich_race_medal"
    assert turn_in.fleet_total == 10   # 1 worn + 8 sibling + 1 banked
    assert turn_in.buyer == "Robby"


def test_no_turn_in_one_medal_short(tmp_path):
    player, store = _player_with(tmp_path, "Robby")
    CoordinationStore(db_path=str(tmp_path / "coord.db"),
                      character="HAL").publish_holdings({"lich_race_medal": 7}, NOW)
    state = make_state(level=27, inventory={}, bank_items={"lich_race_medal": 1},
                       equipment={"artifact1_slot": "lich_race_medal"})

    player._resolve_turn_in(state, player.game_data)

    assert player._turn_in is None


def test_a_character_below_the_item_level_does_not_claim_the_turn_in(tmp_path):
    """lich_race_trophy is level 20. A level-15 buyer would spend the fleet's
    medals on something it cannot wear."""
    player, store = _player_with(tmp_path, "HAL")
    CoordinationStore(db_path=str(tmp_path / "coord.db"),
                      character="Robby").publish_holdings({"lich_race_medal": 9}, NOW)
    state = make_state(level=15, inventory={"lich_race_medal": 1})

    player._resolve_turn_in(state, player.game_data)

    assert player._turn_in is None
```

Define `NOW` once at module scope as a UTC datetime; the coordination store rejects naive datetimes.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_player_turn_in.py -v`
Expected: FAIL — `AttributeError: 'GamePlayer' object has no attribute '_resolve_turn_in'`

- [ ] **Step 3: Implement**

`_update_coordination` gains one line publishing `dual_role_holdings(state, game_data)`. `_resolve_turn_in` implements rules 1-5 above, calls `claim_turn_in` only when this character passes rules 3 and 4, stores the result on `self._turn_in`, and computes `self._recall` for non-buyers from `recall_shortfall_pure` and this character's own holdings. `_selection_context` threads both onto `SelectionContext`.

A character that is neither buyer nor holder of any recalled unit gets `turn_in=None, recall=None` and is completely unaffected.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_player_turn_in.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py \
        src/artifactsmmo_cli/ai/selection_context.py \
        tests/test_ai/test_player_turn_in.py
git commit -m "feat(ai): resolve a fleet turn-in and elect its buyer each cycle"
```

---

### Task 6: The means and its two goals

**Files:**
- Create: `src/artifactsmmo_cli/ai/goals/currency_turnin.py` (buyer)
- Create: `src/artifactsmmo_cli/ai/goals/surrender_currency.py` (holder)
- Modify: `src/artifactsmmo_cli/ai/tiers/means.py`
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py`
- Test: `tests/test_ai/test_currency_turnin_goals.py`, `tests/test_ai/test_means_currency_turnin.py`

**Interfaces:**
- Consumes: `SelectionContext.turn_in` / `.recall` (Task 5).
- Produces:
  - `MeansKind.CURRENCY_TURNIN`, appended LAST to the enum (enum identity must stay stable for the DecideKey oracle) and slotted into `COLLECT_REWARD_ORDER` immediately after `SUPPLY_BANK`.
  - `CurrencyTurnInGoal(item_code, npc_code, price, currency)` — buyer side.
  - `SurrenderCurrencyGoal(currency, units)` — holder side.

Why `COLLECT_REWARD_ORDER`: it is above the objective step, so the turn-in does not depend on `J` ever choosing gear — which, per the Evidence section, it never does. It is below every safety guard, so a starving or over-full character still fixes itself first. Same seat and same reasoning as `SUPPLY_BANK`.

- [ ] **Step 1: Write the failing test for the means**

```python
def test_turn_in_fires_for_the_elected_buyer():
    ctx = _ctx(turn_in=TurnIn(item_code="lich_race_trophy", npc_code="archaeologist",
                              price=10, currency="lich_race_medal",
                              buyer="Robby", fleet_total=10))
    assert _fires(MeansKind.CURRENCY_TURNIN, make_state(), medal_game_data(), ctx) is True


def test_turn_in_fires_for_a_holder_asked_to_surrender():
    ctx = _ctx(recall=("lich_race_medal", 2))
    assert _fires(MeansKind.CURRENCY_TURNIN, make_state(), medal_game_data(), ctx) is True


def test_turn_in_is_inert_for_an_uninvolved_character():
    assert _fires(MeansKind.CURRENCY_TURNIN, make_state(), medal_game_data(), _ctx()) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_means_currency_turnin.py -v`
Expected: FAIL — `AttributeError: CURRENCY_TURNIN`

- [ ] **Step 3: Write the failing goal tests**

```python
def test_buyer_plans_withdraw_then_purchase():
    """The last mile already works when the medals are in the bank — this goal
    exists to make the planner be HANDED that goal at all."""
    gd = medal_game_data()
    state = make_state(level=27, inventory={}, bank_items={"lich_race_medal": 10})
    goal = CurrencyTurnInGoal(item_code="lich_race_trophy", npc_code="archaeologist",
                              price=10, currency="lich_race_medal")
    plan = GOAPPlanner().plan(state, goal, _turn_in_actions(gd, state), gd)

    assert [repr(a) for a in plan] == [
        "Withdraw(lich_race_medal×10)",
        "NpcBuy(lich_race_trophy×1@archaeologist)",
    ]


def test_buyer_goal_is_satisfied_once_the_item_is_owned():
    gd = medal_game_data()
    state = make_state(inventory={"lich_race_trophy": 1})
    goal = CurrencyTurnInGoal(item_code="lich_race_trophy", npc_code="archaeologist",
                              price=10, currency="lich_race_medal")
    assert goal.is_satisfied(state) is True


def test_holder_plans_unequip_then_deposit():
    gd = medal_game_data()
    state = make_state(equipment={"artifact1_slot": "lich_race_medal"}, inventory={})
    goal = SurrenderCurrencyGoal(currency="lich_race_medal", units=1)
    plan = GOAPPlanner().plan(state, goal, _turn_in_actions(gd, state), gd)

    assert [repr(a) for a in plan][:2] == ["Unequip(artifact1_slot)",
                                           "DepositItem(lich_race_medal×1)"]


def test_holder_goal_is_satisfied_when_its_units_are_banked():
    gd = medal_game_data()
    state = make_state(inventory={}, equipment={},
                       bank_items={"lich_race_medal": 4})
    goal = SurrenderCurrencyGoal(currency="lich_race_medal", units=1)
    assert goal.is_satisfied(state) is True
```

Read the real `repr` of the deposit action before pinning it — use whatever `actions/bank.py` actually produces rather than the name guessed here.

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_currency_turnin_goals.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.goals.currency_turnin'`

- [ ] **Step 5: Implement both goals and the means wiring**

Each goal is one class in its own file. `relevant_actions` must be narrow — withdraw/npc-buy for the buyer, unequip/deposit for the holder — because a wide pool is what makes these searches expensive. `is_satisfied` for the holder is "my units are in the bank", so a character that already banked them stops immediately and does not chase the trophy it is not buying.

`strategy_driver`'s means-to-goal chain gets one branch: `ctx.recall is not None` selects `SurrenderCurrencyGoal`, otherwise `CurrencyTurnInGoal` from `ctx.turn_in`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_currency_turnin_goals.py tests/test_ai/test_means_currency_turnin.py -v`
Expected: PASS (7 tests)

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/currency_turnin.py \
        src/artifactsmmo_cli/ai/goals/surrender_currency.py \
        src/artifactsmmo_cli/ai/tiers/means.py \
        src/artifactsmmo_cli/ai/strategy_driver.py \
        tests/test_ai/test_currency_turnin_goals.py \
        tests/test_ai/test_means_currency_turnin.py
git commit -m "feat(tiers): turn fleet currency in for the upgrade it pays for"
```

---

### Task 7: Do not re-wear what is mid-flight

**Files (as built — see note after Step 3):**
- Modify: `src/artifactsmmo_cli/ai/equipment/empty_slot_fills.py`
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py`
- Test: `tests/test_ai/test_turn_in_no_livelock.py`

**Interfaces:**
- Consumes: `SelectionContext.turn_in` (Task 5).
- Produces: no new API — an additional exclusion inside the existing fill/keep predicates, live only while `ctx.turn_in` is set.

This is the narrow version of "don't equip". Equipping dual-role items stays allowed everywhere and always; while a specific turn-in is claimed, its currency code is excluded from empty-slot fills so a surrendered medal is not immediately re-worn by the character that just banked it. Withdraw-then-re-equip loops are this repo's known livelock shape.

- [ ] **Step 1: Write the failing test**

```python
def test_a_recalled_currency_is_not_re_equipped_while_the_turn_in_is_live():
    gd = medal_game_data()
    state = make_state(inventory={"lich_race_medal": 1}, equipment={})
    live = _ctx(turn_in=TurnIn(item_code="lich_race_trophy", npc_code="archaeologist",
                               price=10, currency="lich_race_medal",
                               buyer="Robby", fleet_total=10))

    assert empty_slot_rank_fills(state, gd, live) == []


def test_the_same_medal_is_equippable_when_no_turn_in_is_live():
    """The general rule is unchanged: wearing dual-role items IS the storage."""
    gd = medal_game_data()
    state = make_state(inventory={"lich_race_medal": 1}, equipment={})

    fills = empty_slot_rank_fills(state, gd, _ctx())

    assert ("artifact1_slot", "lich_race_medal") in fills
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_turn_in_no_livelock.py -v`
Expected: FAIL — the first test returns the fill, since nothing consults `ctx.turn_in` yet.

- [ ] **Step 3: Implement the exclusion**

`empty_slot_rank_fills` already took a `reserved: frozenset[str]` parameter for the task-reservation pipeline, so no `ctx`-consuming branch was added inside it. Instead, its one call site — `strategy_driver.py`'s `map_means`/candidate-building, where `EquipOwnedGoal.fills` is computed — folds `{ctx.turn_in.currency}` into that same `reserved` set whenever `ctx.turn_in is not None`, alongside the existing `task_reserved_demand(state, game_data)`. A recalled unit is excluded from the fill exactly like a task-reserved item is, through the mechanism that already existed for that purpose — no second reservation channel, and no change to `inventory_keep.py`: the deposit/keep economy was never in this exclusion's path, only the equip-fill one.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_turn_in_no_livelock.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py \
        src/artifactsmmo_cli/ai/equipment/empty_slot_fills.py \
        tests/test_ai/test_turn_in_no_livelock.py
git commit -m "fix(ai): hold recalled currency out of slot fills while a turn-in is live"
```

---

### Task 8: Make it visible, and prove it end to end

**Files:**
- Modify: `src/artifactsmmo_cli/ai/cycle_snapshot.py`
- Modify: `src/artifactsmmo_cli/ai/player.py` (trace emission)
- Test: `tests/test_ai/test_turn_in_scenario.py`

**Interfaces:**
- Consumes: everything above.
- Produces: a `turn_in` block in the per-cycle trace: `{"item": ..., "currency": ..., "price": ..., "fleet_total": ..., "buyer": ..., "role": "buyer" | "holder" | null}`.

- [ ] **Step 1: Write the failing scenario test**

```python
def test_five_characters_wearing_ten_medals_reach_the_trophy(tmp_path):
    """The whole point, end to end: nobody is told to stop wearing medals, and
    the fleet still converts them.

    Robby (level 27, the only character that can wear a level-20 trophy) is
    elected; HAL and R2D2 each surrender what they wear; the bank supplies the
    rest."""
    db = str(tmp_path / "coord.db")
    gd = medal_game_data()
    for name, worn in (("HAL", 3), ("R2D2", 3)):
        CoordinationStore(db_path=db, character=name).publish_holdings(
            {"lich_race_medal": worn}, NOW)

    robby = _player(db, "Robby", make_state(
        level=27, equipment={"artifact1_slot": "lich_race_medal"},
        inventory={}, bank_items={"lich_race_medal": 3}))
    robby._resolve_turn_in(robby.state, gd)

    assert robby._turn_in.item_code == "lich_race_trophy"
    goal, plan, _ = robby._decide_band(robby.state, gd, robby._build_actions(), None)
    assert isinstance(goal, CurrencyTurnInGoal)
    assert plan, "the elected buyer must produce a plan, not just a goal"

    hal = _player(db, "HAL", make_state(
        level=15, equipment={"artifact1_slot": "lich_race_medal"}, inventory={}))
    hal._resolve_turn_in(hal.state, gd)
    hal_goal, hal_plan, _ = hal._decide_band(hal.state, gd, hal._build_actions(), None)

    assert isinstance(hal_goal, SurrenderCurrencyGoal)
    assert [repr(a) for a in hal_plan][0] == "Unequip(artifact1_slot)"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_turn_in_scenario.py -v`
Expected: FAIL — until the trace fields and the full wiring exist.

- [ ] **Step 3: Add the trace fields and finish the wiring**

Add to `CycleSnapshot`, beside the existing `supply_target` field and following its
docstring convention (one field, one reader, named):

```python
    turn_in: dict[str, object] | None = None
    """The fleet currency turn-in this character is party to, or None.

    Keys: `item`, `currency`, `price`, `fleet_total`, `buyer`, `role`
    (`"buyer"` / `"holder"` / None). Emitted on EVERY character, including the
    uninvolved ones (as None), so a trace reader can tell "no turn-in was
    possible" apart from "this child never looked" — the distinction that cost
    the lich-medal investigation its first two hours."""
```

`GamePlayer` fills it from `self._turn_in` / `self._recall` at the same point it
fills `supply_target`.

- [ ] **Step 4: Run the scenario and the whole AI suite**

Run: `uv run pytest tests/test_ai/test_turn_in_scenario.py -v` then `uv run pytest tests/test_ai -q`
Expected: PASS, no new failures anywhere.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/cycle_snapshot.py \
        src/artifactsmmo_cli/ai/player.py \
        tests/test_ai/test_turn_in_scenario.py
git commit -m "feat(trace): surface the fleet turn-in, and prove it end to end"
```

---

### Task 9: Pay the formal and mutation debts

**Files:**
- Modify: `formal/Formal/Liveness/MeansFiring.lean`
- Modify: `formal/diff/mutate.py`
- Test: `bash formal/gate.sh`

A new `MeansKind` owes the liveness ladder a rung: the proofs enumerate the means and a new constructor breaks the exhaustiveness the ladder relies on. Budget real time for this — this repo's history is explicit that a new means or guard kind is never free.

- [ ] **Step 1: Run the gate and read the Lean failure**

Run: `bash formal/gate.sh > /tmp/gate.log 2>&1; echo $?`
Expected: non-zero, with a Lean error naming the non-exhaustive match over `MeansKind`.

- [ ] **Step 2: Add the rung**

`CURRENCY_TURNIN` fires only when `ctx.turn_in` or `ctx.recall` is set, both of which are None on every single-character run, so the rung's hypothesis is the same shape as `SUPPLY_BANK`'s. Model it on that one. The hypothesis must be SATISFIABLE — a vacuous liveness rung is worse than none, and this repo has shipped several.

- [ ] **Step 3: Add mutation coverage**

Three mutants, each in its own group, each killed by a named test:
- threshold `>=` → `>` in `turn_in_ready_pure` (killed by the boundary parametrize in Task 3)
- `recall_shortfall_pure` dropping the bank term (killed by `test_shortfall_counts_only_what_the_buyer_cannot_reach_alone`)
- `dual_role_holdings` counting inventory only, not worn (killed by `test_holdings_count_worn_and_carried_together`)

- [ ] **Step 4: Verify anchors and run the sweep**

Run: `uv run python formal/diff/mutate.py --check-anchors` then `uv run python formal/diff/mutate.py --only currency_turnin,dual_role`
Expected: anchors resolve uniquely; every new mutant killed.

- [ ] **Step 5: Run the full gate**

Run: `bash formal/gate.sh > /tmp/gate.log 2>&1; echo $?`
Expected: 0, `ALL GATE PARTS PASSED`, 100.00% coverage.

- [ ] **Step 6: Commit**

```bash
git add formal/ && git commit -m "feat(formal): liveness rung and mutants for the currency turn-in"
```

---

## Verification before calling this done

- [ ] `bash formal/gate.sh` exits 0 with `ALL GATE PARTS PASSED` and 100.00% coverage.
- [ ] `uv run pytest tests/test_multi tests/test_utils -q` passes (pre-commit does not cover these).
- [ ] Live activation, not just green tests: run `uv run artifactsmmo play <name> --dry-run -v` for a character the fleet has elected and confirm the turn-in appears in the trace. Green tests have repeatedly not meant a runtime-active feature in this repo.
- [ ] The live fleet actually converts: after deploying, check that `lich_race_trophy` appears in a character's artifact slot and that `event_ticket` stock resumes climbing.

## Known limits this plan does NOT remove

1. **Accumulation stays one medal per plan.** A demand of 2+ medals emits a single batched `NpcBuy` needing 200+ tickets against a 152-quantity bag. The fleet reaches 10 medals only because each character buys one for each empty artifact slot. If that proves too slow, the fix is repeated purchase-and-bank in the acquisition model — a separate plan.
2. **`J` still ranks every gear candidate as tied at reach 30.** The turn-in works because it fires above the objective step, not because the pivot was fixed. The pivot remains wrong for every other gear decision.
3. **The trophy is level 20**, so only characters at or above that level can be elected buyer. With the current fleet that is Robby alone.

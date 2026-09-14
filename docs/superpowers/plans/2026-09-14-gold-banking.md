# Gold Banking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Characters bank whole 10,000-gold chunks of surplus pocket gold during the bank trips they already make, and the TUI shows bank gold separately from carried gold.

**Architecture:** One pure arithmetic core (`ai/gold_surplus_core.py`) decides how much gold is bankable. `DepositAllAction` — already the bank trip for items — calls it and issues one extra `action_deposit_gold` request when a chunk is due. No new goal, no new action, no ladder rung, no Lean change. `CycleSnapshot` gains a `bank_gold` field so three TUI render sites can show a number that has never crossed the process boundary.

**Tech Stack:** Python 3.13, `uv`, pytest, SQLModel/SQLite (`learning.db`), Textual + Rich (TUI), Lean 4 (`formal/`), `formal/diff/mutate.py` (mutation gate).

**Spec:** `docs/superpowers/specs/2026-09-14-gold-banking-design.md`

## Global Constraints

- Run every Python command through `uv run` (e.g. `uv run pytest`, `uv run mypy`).
- One behavioral class per file. Pure-function modules may hold several functions.
- All imports at the top of the file. No inline imports. No `if TYPE_CHECKING`.
- Never catch bare `Exception`. Never add a second layer of error handling.
- Use only API data or fail with an error — no defaulting around missing game data.
- Tests live in `tests/`. Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- `GOLD_CHUNK = 10_000`.
- `TRIGGER_FILL_NUM = 75`, `TRIGGER_FILL_DEN = 100` (live values in `bank_expansion_timing.py`).
- Expansion hold threshold: `HOLD_FILL_NUM = 70`, `HOLD_FILL_DEN = 100` — must equal `ExpandBankGoal._SATISFIED_FILL` (0.70).
- Fill comparisons use exact integer cross-multiply, never float (house rule in `bank_expansion_timing.py`).
- Commit messages end with the two attribution lines used throughout this repo:
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01Ncwushdsr3ba3zkzgSrbsR`.

## File Structure

| file | responsibility |
|---|---|
| `src/artifactsmmo_cli/ai/gold_surplus_core.py` | **Create.** Pure arithmetic: `bankable_gold`, `expansion_hold`, `GOLD_CHUNK`. Takes ints, returns ints, imports nothing from the project. |
| `src/artifactsmmo_cli/ai/bank_expansion_timing.py` | **Modify.** Add `HOLD_FILL_NUM`/`HOLD_FILL_DEN` beside the trigger pair it already owns. |
| `src/artifactsmmo_cli/ai/goals/expand_bank.py` | **Modify.** Fix the stale "95/100" comment; derive nothing, assert agreement in a test. |
| `src/artifactsmmo_cli/ai/actions/deposit_all.py` | **Modify.** Compose the keep, extend `apply`, issue the gold request in `execute`. |
| `src/artifactsmmo_cli/ai/cycle_snapshot.py` | **Modify.** Add `bank_gold: int \| None = None`. |
| `src/artifactsmmo_cli/ai/player.py` | **Modify.** Feed `bank_gold` at the one snapshot construction site. |
| `src/artifactsmmo_cli/tui/widgets/status_pane.py` | **Modify.** Relabel the gold row. |
| `src/artifactsmmo_cli/tui/screens/character_screen.py` | **Modify.** Relabel the gold row. |
| `src/artifactsmmo_cli/tui/item_tables.py` | **Modify.** Bank header carries gold. |
| `src/artifactsmmo_cli/audit/liveness_completeness.py` | **Modify.** Reword `DepositGoldAction`'s dormancy reason. |
| `formal/diff/mutate.py` | **Modify.** Add `GOLD_SURPLUS_MUTATIONS`. |

---

### Task 1: The pure arithmetic core

**Files:**
- Create: `src/artifactsmmo_cli/ai/gold_surplus_core.py`
- Test: `tests/test_ai/test_gold_surplus_core.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `GOLD_CHUNK: int`, `bankable_gold(pocket: int, reserve: int, chunk: int = GOLD_CHUNK) -> int`, `expansion_hold(bank_used: int, bank_capacity: int, next_expansion_cost: int, hold_num: int, hold_den: int) -> int`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai/test_gold_surplus_core.py`:

```python
"""How much pocket gold is surplus, and how much an imminent expansion holds back.

Gold is per-character; the bank is the account-wide pool. Across 184,010 cycles
the fleet never moved gold between them, so Lor carried 28,016 while Robby
carried 1,672 on one account. This module decides what moves.

THE KEPT REMAINDER IS THE POINT. `GatherMaterialsGoal` admits a deficit-sized
`WithdrawGold` (the GAP-3 ferry, gathering.py:613). Banking everything above the
reserve would let that ferry pull the gold straight back next cycle — the
`Withdraw`/`DepositAll` oscillation this codebase has already shipped once. Only
whole chunks move, so the ferry must drain a full chunk of slack before another
is eligible.
"""

from artifactsmmo_cli.ai.gold_surplus_core import (
    GOLD_CHUNK,
    bankable_gold,
    expansion_hold,
)


def test_chunk_is_ten_thousand():
    assert GOLD_CHUNK == 10_000


def test_below_one_chunk_above_the_reserve_banks_nothing():
    assert bankable_gold(pocket=12_999, reserve=3_000) == 0


def test_exactly_one_chunk_above_the_reserve_banks_one():
    assert bankable_gold(pocket=13_000, reserve=3_000) == 10_000


def test_the_remainder_is_always_kept():
    """Lor's live case: 28,016 pocket, 3,000 reserve -> bank 20,000, keep 8,016."""
    assert bankable_gold(pocket=28_016, reserve=3_000) == 20_000


def test_a_reserve_above_the_pocket_banks_nothing():
    """Saving for something out of reach is a real state, not an error."""
    assert bankable_gold(pocket=500, reserve=9_000) == 0


def test_a_reserve_equal_to_the_pocket_banks_nothing():
    assert bankable_gold(pocket=9_000, reserve=9_000) == 0


def test_banking_never_breaches_the_reserve():
    """The property, not a case: whatever is banked, the reserve survives."""
    for pocket in range(0, 60_001, 997):
        for reserve in (0, 100, 3_000, 9_999, 25_000):
            kept = pocket - bankable_gold(pocket, reserve)
            assert kept >= min(reserve, pocket), (pocket, reserve, kept)


def test_banked_amount_is_always_a_whole_number_of_chunks():
    for pocket in range(0, 60_001, 997):
        assert bankable_gold(pocket, 3_000) % GOLD_CHUNK == 0


def test_no_expansion_hold_below_the_threshold():
    """69 of 100 slots is under 70% — the expansion is not in play yet."""
    assert expansion_hold(bank_used=69, bank_capacity=100,
                          next_expansion_cost=3_500,
                          hold_num=70, hold_den=100) == 0


def test_expansion_holds_the_cost_at_the_threshold():
    assert expansion_hold(bank_used=70, bank_capacity=100,
                          next_expansion_cost=3_500,
                          hold_num=70, hold_den=100) == 3_500


def test_expansion_holds_the_cost_above_the_threshold():
    assert expansion_hold(bank_used=95, bank_capacity=100,
                          next_expansion_cost=3_500,
                          hold_num=70, hold_den=100) == 3_500


def test_unknown_capacity_holds_nothing():
    """Capacity 0 means capacity was never read. UNKNOWN IS NOT FULL."""
    assert expansion_hold(bank_used=70, bank_capacity=0,
                          next_expansion_cost=3_500,
                          hold_num=70, hold_den=100) == 0


def test_the_fill_comparison_is_exact_at_the_boundary():
    """7 of 10 is exactly 70%: an int-truncating comparison would miss it, and a
    float one would be a house-rule violation."""
    assert expansion_hold(bank_used=7, bank_capacity=10,
                          next_expansion_cost=3_500,
                          hold_num=70, hold_den=100) == 3_500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_gold_surplus_core.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.gold_surplus_core'`

- [ ] **Step 3: Write minimal implementation**

Create `src/artifactsmmo_cli/ai/gold_surplus_core.py`:

```python
"""Pure arithmetic for what pocket gold is surplus to a character's needs.

No I/O and no project imports: every input is an int the caller has already
measured, which is what makes this property-testable over whole ranges rather
than case by case. The impure composition — which reserve, which fill — lives in
`DepositAllAction`.
"""

GOLD_CHUNK = 10_000
"""Gold moves between pocket and bank in whole units of this size.

CHUNKING IS HYSTERESIS, NOT TIDINESS. `GatherMaterialsGoal.relevant_actions`
admits a deficit-sized `WithdrawGold` whenever pocket gold cannot cover a plan's
gold-priced leaves (the GAP-3 ferry, gathering.py:613). A rule that banked every
coin above the reserve would let that ferry withdraw gold the same trip banked,
and the pair would trade one coin forever — the `Withdraw`/`DepositAll`
oscillation this codebase has already shipped once. Keeping the sub-chunk
remainder means the ferry must drain a full chunk of slack before another chunk
is eligible to leave.
"""


def bankable_gold(pocket: int, reserve: int, chunk: int = GOLD_CHUNK) -> int:
    """Whole `chunk` units of `pocket` above `reserve`; 0 when short.

    Guarantees `pocket - bankable_gold(pocket, reserve) >= reserve` whenever the
    pocket can cover the reserve at all — the invariant that makes banking
    unable to breach a reservation.
    """
    return max(0, (pocket - reserve) // chunk) * chunk


def expansion_hold(bank_used: int, bank_capacity: int, next_expansion_cost: int,
                   hold_num: int, hold_den: int) -> int:
    """`next_expansion_cost` while a bank expansion is in play, else 0.

    A BANK EXPANSION IS NEVER A RESERVED GEAR CODE — `ExpandBankGoal.value` says
    so — and `reserved_targets` reserves only the cheapest unmet ITEM purchase.
    So nothing else protects the gold an expansion needs, and banking the pocket
    empty would starve it silently: `expansion_fires` requires `pocket_gold >=
    cost`, so the rung simply never fires. No error, no plan, and a bank that
    cannot expand is a livelock this fleet has already hit.

    A WITHDRAW FERRY CANNOT FIX THAT, which is why the hold is here instead.
    Both `ExpandBankGoal.value` and the arbiter's BANK_EXPAND guard call the
    same `expansion_fires`, so a pocket-short character's goal returns 0.0 and
    its `relevant_actions` is never consulted — nothing would ever ask for the
    gold back.

    Capacity 0 means capacity was never read, and UNKNOWN IS NOT FULL: hold
    nothing rather than invent a fill ratio. Exact integer cross-multiply, no
    float, matching `bank_expansion_timing`.
    """
    if bank_capacity <= 0:
        return 0
    if bank_used * hold_den < bank_capacity * hold_num:
        return 0
    return next_expansion_cost
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_gold_surplus_core.py -q --no-cov`
Expected: PASS, 12 passed

- [ ] **Step 5: Lint and typecheck**

Run: `uv run ruff check src/ tests/ && uv run mypy src/artifactsmmo_cli/ai/gold_surplus_core.py`
Expected: "All checks passed!" and "Success: no issues found in 1 source file"

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/gold_surplus_core.py tests/test_ai/test_gold_surplus_core.py
git commit -m "$(cat <<'EOF'
feat(gold): pure core for what pocket gold is surplus

`bankable_gold` moves whole 10,000-gold chunks above a keep, and keeps
the remainder. The remainder is hysteresis, not tidiness: the live GAP-3
withdraw ferry (gathering.py:613) admits a deficit-sized WithdrawGold
whenever the pocket cannot cover a plan's gold leaves, so banking every
coin above the reserve would let deposit and withdraw trade one coin
forever.

`expansion_hold` holds next_expansion_cost back while bank fill is at or
above the threshold. Nothing else protects that gold — reserved_targets
reserves the cheapest unmet ITEM purchase, and ExpandBankGoal.value says
outright that a bank expansion is never a reserved gear code.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Ncwushdsr3ba3zkzgSrbsR
EOF
)"
```

---

### Task 2: The hold threshold constant

**Files:**
- Modify: `src/artifactsmmo_cli/ai/bank_expansion_timing.py:37-41` (add after the trigger pair)
- Modify: `src/artifactsmmo_cli/ai/goals/expand_bank.py:17-24` (stale comment)
- Test: `tests/test_ai/test_bank_expansion_timing.py` (existing module — append)

**Interfaces:**
- Consumes: Task 1's `expansion_hold` signature (`hold_num`, `hold_den`).
- Produces: `HOLD_FILL_NUM: int = 70`, `HOLD_FILL_DEN: int = 100` importable from `artifactsmmo_cli.ai.bank_expansion_timing`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ai/test_bank_expansion_timing.py`:

```python
def test_hold_threshold_sits_below_the_expansion_trigger():
    """The hold must start BEFORE the expansion wants to fire, or the price is
    still being banked when `expansion_fires` asks for it."""
    from artifactsmmo_cli.ai.bank_expansion_timing import (
        HOLD_FILL_DEN,
        HOLD_FILL_NUM,
        TRIGGER_FILL_DEN,
        TRIGGER_FILL_NUM,
    )
    assert HOLD_FILL_NUM * TRIGGER_FILL_DEN < TRIGGER_FILL_NUM * HOLD_FILL_DEN


def test_hold_threshold_equals_the_goal_satisfaction_mark():
    """One fill ratio, two roles: ExpandBankGoal stops WANTING to expand below
    it, and the deposit stops banking the price above it. If they drift, a
    character can be unsatisfied-and-unfunded in the gap between them."""
    from artifactsmmo_cli.ai.bank_expansion_timing import HOLD_FILL_DEN, HOLD_FILL_NUM
    from artifactsmmo_cli.ai.goals.expand_bank import _SATISFIED_FILL

    assert HOLD_FILL_NUM / HOLD_FILL_DEN == _SATISFIED_FILL
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_bank_expansion_timing.py -q --no-cov -k hold`
Expected: FAIL — `ImportError: cannot import name 'HOLD_FILL_NUM'`

- [ ] **Step 3: Add the constants**

In `src/artifactsmmo_cli/ai/bank_expansion_timing.py`, immediately after the
`TRIGGER_FILL_NUM`/`TRIGGER_FILL_DEN` block and its docstring, add:

```python
HOLD_FILL_NUM = 70
HOLD_FILL_DEN = 100
"""The fill at which a character stops banking the next expansion's price (70%).

BELOW THE TRIGGER ON PURPOSE. `expansion_fires` requires the POCKET to cover
`cost`, so gold banked away is gold the expansion cannot use, and there is no
withdraw-gold edge to fetch it back (see this module's docstring: the
executability conjunct exists precisely because there is none). Holding the
price from here gives the pocket a runway to be funded before the trigger
arrives.

EQUAL TO `ExpandBankGoal._SATISFIED_FILL`, and that is the invariant, not a
coincidence: below that mark the goal does not want an expansion, so there is
nothing to save for; at or above it there is. A test pins the two together so
neither can drift.
"""
```

- [ ] **Step 4: Fix the stale comment in `expand_bank.py`**

`expand_bank.py:16-17` currently reads:

```python
# value() activates at or above the shared TRIGGER_FILL_NUM/DEN ratio (95/100,
# owned by bank_expansion_timing; exact integer cross-multiply — no float).
```

The live constant is `75`, not `95`. Replace those two lines with:

```python
# value() activates at or above the shared TRIGGER_FILL_NUM/DEN ratio (75/100,
# owned by bank_expansion_timing; exact integer cross-multiply — no float).
# The 95/100 this comment claimed until 2026-09-14 was never the constant's
# value; `_SATISFIED_FILL`'s own "five points under the trigger" note is right.
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_bank_expansion_timing.py -q --no-cov`
Expected: PASS, all tests in the module

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/bank_expansion_timing.py src/artifactsmmo_cli/ai/goals/expand_bank.py tests/test_ai/test_bank_expansion_timing.py
git commit -m "$(cat <<'EOF'
feat(gold): the fill at which a character stops banking the expansion price

HOLD_FILL_NUM/DEN (70/100) joins the trigger pair in the module that
already owns "should the bank expand", so the deposit side and the
expansion side cannot re-type the ratio apart. Pinned by test to
ExpandBankGoal._SATISFIED_FILL: below that mark the goal does not want an
expansion and there is nothing to save for.

Also corrects a stale comment in expand_bank.py claiming the trigger is
95/100. It is 75/100, and _SATISFIED_FILL's own "five points under the
trigger" note was already right.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Ncwushdsr3ba3zkzgSrbsR
EOF
)"
```

---

### Task 3: `DepositAllAction` banks the gold

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/deposit_all.py`
- Test: `tests/test_ai/test_deposit_all_gold.py` (create)

**Interfaces:**
- Consumes: Task 1 `bankable_gold`, `expansion_hold`; Task 2 `HOLD_FILL_NUM`, `HOLD_FILL_DEN`; existing `progression_reserve(state, game_data) -> int`; existing `wait_out_cooldown(state)`.
- Produces: `DepositAllAction._gold_deposit(state) -> int`; `apply` and `execute` both move gold.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai/test_deposit_all_gold.py`:

```python
"""`DepositAllAction` is the BANK TRIP, not the item-deposit trip.

The liveness census has excused `DepositGoldAction` since it was written with
"gold is banked by DepositAll, not as a separate step". That was false —
`execute` called `deposit_item` and nothing else, and across 184,010 cycles no
character ever banked a coin. This makes the claim true.

Gold rides a trip items justify and never causes one: `is_applicable` stays
items-only, so `value`, `is_satisfied` and `desired_state` on
`DepositInventoryGoal` are untouched and both Lean theorems over them still bind.
"""

from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state

BANK = (4, 0)


def _gd(bank_capacity: int = 200, next_expansion_cost: int = 3_500) -> GameData:
    gd = GameData()
    gd._item_stats = {"copper_ore": ItemStats(code="copper_ore", level=1, type_="resource")}
    gd._npc_stock = {"merchant": {"copper_ore": 5}}
    gd._monster_level = {"chicken": 1}
    gd._bank_capacity = bank_capacity
    gd._next_expansion_cost = next_expansion_cost
    return gd


def _action(gd: GameData | None) -> DepositAllAction:
    return DepositAllAction(bank_location=BANK, accessible=True, game_data=gd)


def _state(gold: int, bank_gold: int = 0, banked_codes: int = 0):
    bank = {f"slot{i}": 1 for i in range(banked_codes)}
    return make_state(x=BANK[0], y=BANK[1], gold=gold,
                      inventory={"copper_ore": 40}, inventory_max=200,
                      bank_items=bank, bank_gold=bank_gold)


def test_a_surplus_chunk_is_banked():
    gd = _gd()
    action = _action(gd)
    # reserve is the safety floor (100) for a state with no gear targets.
    assert action._gold_deposit(_state(gold=28_016)) == 20_000


def test_no_chunk_means_no_gold_moves():
    gd = _gd()
    assert _action(gd)._gold_deposit(_state(gold=9_999)) == 0


def test_no_game_data_banks_no_gold():
    """No game data means no reserve can be computed. Use only API data or fail
    — never default the reserve to zero and bank a character dry."""
    assert _action(None)._gold_deposit(_state(gold=28_016)) == 0


def test_an_imminent_expansion_holds_its_price_back():
    """Bank at 70% of capacity: the expansion price stops being bankable."""
    gd = _gd(bank_capacity=100, next_expansion_cost=15_000)
    action = _action(gd)
    state = _state(gold=28_016, banked_codes=70)
    assert action._gold_deposit(state) == 10_000


def test_a_distant_expansion_holds_nothing_back():
    gd = _gd(bank_capacity=100, next_expansion_cost=15_000)
    action = _action(gd)
    state = _state(gold=28_016, banked_codes=69)
    assert action._gold_deposit(state) == 20_000


def test_apply_moves_gold_and_bank_gold_together():
    """`apply` and `execute` must tell the same story — this file's comments
    defend that invariant twice already for items."""
    gd = _gd()
    action = _action(gd)
    state = _state(gold=28_016, bank_gold=5_000)
    after = action.apply(state, gd)
    assert after.gold == 8_016
    assert after.bank_gold == 25_000


def test_apply_leaves_gold_alone_when_no_chunk_is_due():
    gd = _gd()
    action = _action(gd)
    state = _state(gold=9_999, bank_gold=5_000)
    after = action.apply(state, gd)
    assert after.gold == 9_999
    assert after.bank_gold == 5_000


def test_execute_issues_the_gold_request_after_the_items():
    gd = _gd()
    action = _action(gd)
    state = _state(gold=28_016)
    char = MagicMock()
    char.name = "testchar"
    result = MagicMock()
    result.data = MagicMock()
    result.data.character = char

    with patch("artifactsmmo_cli.ai.actions.deposit_all.WorldState.from_character_schema",
               return_value=state), \
         patch("artifactsmmo_cli.ai.actions.deposit_all.deposit_item",
               return_value=result) as items, \
         patch("artifactsmmo_cli.ai.actions.deposit_all.action_deposit_gold",
               return_value=result) as gold, \
         patch("artifactsmmo_cli.ai.actions.deposit_all.wait_out_cooldown"):
        action.execute(state, MagicMock())

    assert items.called
    assert gold.call_count == 1
    assert gold.call_args.kwargs["body"].quantity == 20_000


def test_execute_issues_no_gold_request_when_no_chunk_is_due():
    """The per-IP request budget is the fleet's binding constraint — a request
    that moves nothing is a request not worth making."""
    gd = _gd()
    action = _action(gd)
    state = _state(gold=9_999)
    char = MagicMock()
    char.name = "testchar"
    result = MagicMock()
    result.data = MagicMock()
    result.data.character = char

    with patch("artifactsmmo_cli.ai.actions.deposit_all.WorldState.from_character_schema",
               return_value=state), \
         patch("artifactsmmo_cli.ai.actions.deposit_all.deposit_item",
               return_value=result), \
         patch("artifactsmmo_cli.ai.actions.deposit_all.action_deposit_gold") as gold, \
         patch("artifactsmmo_cli.ai.actions.deposit_all.wait_out_cooldown"):
        action.execute(state, MagicMock())

    gold.assert_not_called()


def test_is_applicable_still_ignores_gold():
    """Gold rides a trip items justify; it never causes one. If this flips, the
    goal's desired_state (inventory_used only) no longer describes the action."""
    gd = _gd()
    action = _action(gd)
    state = make_state(x=BANK[0], y=BANK[1], gold=999_999,
                       inventory={}, inventory_max=200,
                       bank_items={}, bank_gold=0)
    assert action.is_applicable(state, gd) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_deposit_all_gold.py -q --no-cov`
Expected: FAIL — `AttributeError: 'DepositAllAction' object has no attribute '_gold_deposit'`

- [ ] **Step 3: Add the imports**

In `src/artifactsmmo_cli/ai/actions/deposit_all.py`, add to the API-client import
block (after the `deposit_item` import):

```python
from artifactsmmo_api_client.api.my_characters.action_deposit_bank_gold_my_name_action_bank_deposit_gold_post import (
    sync as action_deposit_gold,
)
from artifactsmmo_api_client.models.deposit_withdraw_gold_schema import DepositWithdrawGoldSchema
```

and to the project import block (keep alphabetical order within the block):

```python
from artifactsmmo_cli.ai.bank_expansion_timing import HOLD_FILL_DEN, HOLD_FILL_NUM
from artifactsmmo_cli.ai.gold_surplus_core import bankable_gold, expansion_hold
from artifactsmmo_cli.ai.progression_reserve import progression_reserve
```

`npc.py`, `ge_fill_sell.py` and `ge_post_buy.py` already import `progression_reserve`
from an action module, so this introduces no new import cycle.

- [ ] **Step 4: Add `_gold_deposit`**

Insert immediately after `_acceptable` and before `is_applicable`:

```python
    def _gold_deposit(self, state: WorldState) -> int:
        """Whole chunks of pocket gold this trip should bank; 0 when none.

        THE KEEP IS THE WIDER OF TWO CLAIMS. `progression_reserve` protects the
        next item purchase; `expansion_hold` protects the next bank expansion,
        which `reserved_targets` never covers because an expansion is not an item
        code. Taking the max means neither can be spent by banking.

        NO GAME DATA, NO BANKING — the same rule `_deposits` follows. The reserve
        cannot be computed without it, and defaulting it to zero would bank a
        character dry.
        """
        if self.game_data is None:
            return 0
        hold = expansion_hold(
            len(state.bank_items or {}), self.game_data.bank_capacity,
            self.game_data.next_expansion_cost, HOLD_FILL_NUM, HOLD_FILL_DEN)
        keep = max(progression_reserve(state, self.game_data), hold)
        return bankable_gold(state.gold, keep)
```

- [ ] **Step 5: Extend `apply`**

In `apply`, replace the final `return dataclasses.replace(...)` call with:

```python
        gold_moved = self._gold_deposit(state)
        return dataclasses.replace(
            state,
            x=dest[0],
            y=dest[1],
            inventory=new_inventory,
            cooldown_expires=None,
            bank_items=new_bank,
            gold=state.gold - gold_moved,
            bank_gold=(None if state.bank_gold is None
                       else state.bank_gold + gold_moved),
        )
```

A `None` `bank_gold` means the bank balance was never read; it stays None rather
than becoming a number nobody observed.

- [ ] **Step 6: Extend `execute`**

In `execute`, replace the final `return last_state` with:

```python
        gold_moved = self._gold_deposit(state)
        if gold_moved:
            # AFTER the items, and only when a chunk is actually due. The gold
            # endpoint starts its own cooldown like every other action, so the
            # last item batch's cooldown has to be slept out first — the same
            # composite-action idiom the batch loop above uses.
            wait_out_cooldown(last_state)
            result = action_deposit_gold(
                client=client, name=state.character,
                body=DepositWithdrawGoldSchema(quantity=gold_moved))
            result = Action._raise_for_error(result, f"DepositGold {gold_moved}")
            last_state = WorldState.from_character_schema(
                result.data.character,
                bank_items=last_state.bank_items,
                bank_gold=last_state.bank_gold,
                pending_items=last_state.pending_items,
                active_events=last_state.active_events,
            )
        return last_state
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_deposit_all_gold.py tests/test_ai/test_deposit_all_batching.py tests/test_ai/test_deposit_all_bank_full.py tests/test_ai/test_actions_execute.py -q --no-cov`
Expected: PASS, all

- [ ] **Step 8: Verify the untouched goal is genuinely untouched**

Run: `uv run pytest tests/test_ai/test_goals.py formal/diff/test_apply_baseline_diff.py -q --no-cov`
Expected: PASS. `BASELINE_FIELDS` is the combat-stat set, so a gold delta in
`apply` must not trip it. If it does, STOP — the spec's "no Lean change" claim
is wrong and needs re-deciding, not patching.

- [ ] **Step 9: Lint and typecheck**

Run: `uv run ruff check src/ tests/ && uv run mypy src/artifactsmmo_cli/ai/actions/deposit_all.py`
Expected: "All checks passed!" and "Success: no issues found in 1 source file"

- [ ] **Step 10: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/deposit_all.py tests/test_ai/test_deposit_all_gold.py
git commit -m "$(cat <<'EOF'
feat(gold): the bank trip banks gold, not just items

DepositAllAction moves whole 10,000-gold chunks above a keep, on the trip
it already makes for items. The keep is max(progression_reserve,
expansion_hold): the first protects the next item purchase, the second
protects a bank expansion, which reserved_targets never covers because an
expansion is not an item code.

is_applicable stays items-only, so gold rides a trip items justify and
never causes one. DepositInventoryGoal's value, is_satisfied and
desired_state are untouched, and both Lean theorems over them still bind.

This makes the liveness census's long-standing claim — "gold is banked by
DepositAll, not as a separate step" — true for the first time.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Ncwushdsr3ba3zkzgSrbsR
EOF
)"
```

---

### Task 4: Hysteresis against the withdraw ferry

**Files:**
- Test: `tests/test_ai/test_gold_banking_hysteresis.py` (create)

**Interfaces:**
- Consumes: Task 1 `bankable_gold`, `GOLD_CHUNK`; Task 3 `DepositAllAction._gold_deposit`.
- Produces: nothing — this task is the regression barrier for the oscillation.

- [ ] **Step 1: Write the test**

Create `tests/test_ai/test_gold_banking_hysteresis.py`:

```python
"""Deposit and withdraw must not trade the same coin.

`GatherMaterialsGoal.relevant_actions` admits a deficit-sized `WithdrawGold`
whenever pocket gold cannot cover a plan's gold-priced leaves (the GAP-3 ferry,
gathering.py:613). That ferry is live and correct. The risk is the PAIR: bank
every coin above the reserve and the ferry withdraws it back next cycle, which is
the `Withdraw`/`DepositAll` oscillation this codebase has already shipped once
(`project_junk_inventory_livelock`).

Asserted as an invariant over a range rather than as one worked example — a
recurring defect in this repo is asserting over a range whose ENDS were never
checked.
"""

from artifactsmmo_cli.ai.gold_surplus_core import GOLD_CHUNK, bankable_gold


def test_a_withdrawal_smaller_than_a_chunk_cannot_re_trigger_a_deposit():
    """Bank, then let the ferry take back anything under a chunk. Nothing is
    bankable again until a full chunk of new slack exists."""
    reserve = 3_000
    for pocket in range(reserve, reserve + 5 * GOLD_CHUNK, 313):
        banked = bankable_gold(pocket, reserve)
        kept = pocket - banked
        for withdrawal in (1, 100, GOLD_CHUNK - 1):
            after_ferry = kept + withdrawal
            assert bankable_gold(after_ferry, reserve) == 0, (
                f"pocket={pocket} banked={banked} kept={kept} "
                f"withdrawal={withdrawal} re-banks immediately")


def test_the_kept_remainder_is_always_under_one_chunk_above_the_reserve():
    """The slack the ferry draws on, bounded: never less than 0, never a whole
    chunk (which would have been banked)."""
    reserve = 3_000
    for pocket in range(reserve, reserve + 10 * GOLD_CHUNK, 271):
        slack = pocket - bankable_gold(pocket, reserve) - reserve
        assert 0 <= slack < GOLD_CHUNK, (pocket, slack)


def test_the_boundary_ends_are_checked_explicitly():
    """Both ends of the ranges above, named so a range-off-by-one cannot hide."""
    reserve = 3_000
    assert bankable_gold(reserve, reserve) == 0
    assert bankable_gold(reserve + GOLD_CHUNK - 1, reserve) == 0
    assert bankable_gold(reserve + GOLD_CHUNK, reserve) == GOLD_CHUNK
    assert bankable_gold(reserve + 2 * GOLD_CHUNK - 1, reserve) == GOLD_CHUNK
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/test_ai/test_gold_banking_hysteresis.py -q --no-cov`
Expected: PASS, 3 passed. These pass on Task 1's implementation — they are a
regression barrier, not a red-green driver. If any FAILS, the chunking in Task 1
is wrong; fix Task 1 rather than relaxing the assertion.

- [ ] **Step 3: Commit**

```bash
git add tests/test_ai/test_gold_banking_hysteresis.py
git commit -m "$(cat <<'EOF'
test(gold): deposit and withdraw cannot trade the same coin

The GAP-3 withdraw ferry is live. Pairing it with a deposit that banked
every coin above the reserve is the Withdraw/DepositAll oscillation this
codebase has already shipped once. Asserted as an invariant over a range,
with both ends named explicitly.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Ncwushdsr3ba3zkzgSrbsR
EOF
)"
```

---

### Task 5: `bank_gold` crosses the process boundary

**Files:**
- Modify: `src/artifactsmmo_cli/ai/cycle_snapshot.py:165` (beside `bank_items`)
- Modify: `src/artifactsmmo_cli/ai/player.py:2785` (the one construction site)
- Test: `tests/test_ai/test_cycle_snapshot_bank_gold.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `CycleSnapshot.bank_gold: int | None` — Task 6 renders it.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai/test_cycle_snapshot_bank_gold.py`:

```python
"""The TUI cannot show a number that never crosses the boundary.

`CycleSnapshot` carried `gold` (the character's pocket) and `bank_items`, and no
bank gold at all — so the three render sites were not omitting the figure, they
had nothing to omit. Gold is per-character and the bank is the account-wide pool
(`openapi.json`: "The numbers of gold on this character" vs "Quantity of gold in
your bank"), so these are two different facts and both have to travel.
"""

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


def _snap(**overrides) -> CycleSnapshot:
    """Mirrors the `_snap` helper the three tui test modules already use."""
    base = dict(
        cycle_index=1, timestamp="2026-05-21T12:00:00Z", character="hero",
        x=0, y=0, level=5, xp=50, max_xp=500, hp=100, max_hp=100, gold=8_016,
        selected_goal="g", action="a", outcome="ok",
    )
    base.update(overrides)
    return CycleSnapshot(**base)


def test_bank_gold_travels_on_the_snapshot():
    assert _snap(bank_gold=20_000).bank_gold == 20_000


def test_bank_gold_defaults_to_none_for_snapshots_that_predate_it():
    """Unknown, not zero. A snapshot serialized before this field existed must
    still validate, the rule `path_blocked` and the region field already rely on."""
    assert _snap().bank_gold is None


def test_pocket_gold_and_bank_gold_are_separate_fields():
    """A single `gold` field would make the two indistinguishable downstream."""
    snap = _snap(gold=8_016, bank_gold=20_000)
    assert (snap.gold, snap.bank_gold) == (8_016, 20_000)
```


- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_cycle_snapshot_bank_gold.py -q --no-cov`
Expected: FAIL — pydantic rejects the unknown field `bank_gold`, or
`AttributeError` on the default case.

- [ ] **Step 3: Add the field**

In `src/artifactsmmo_cli/ai/cycle_snapshot.py`, directly after the `bank_items`
line in the "Committed strategy root + ranking + bank" block:

```python
    bank_gold: int | None = None
    """Gold in the BANK, or None when the bank has not been read this cycle.

    Distinct from `gold`, which is the character's pocket. `openapi.json` scopes
    them differently — "The numbers of gold on this character" versus "Quantity
    of gold in your bank" — so one is per-character and the other is the
    account-wide pool every character shares.

    NULLABLE AND NOT DEFAULTED TO 0: a snapshot written before this field
    existed must still validate, and an unread balance rendered as 0 would claim
    an observation nobody made.
    """
```

- [ ] **Step 4: Feed it at the construction site**

In `src/artifactsmmo_cli/ai/player.py`, in the `CycleSnapshot(...)` call, directly
after the `bank_items=` argument:

```python
            bank_gold=self.state.bank_gold,
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_cycle_snapshot_bank_gold.py -q --no-cov`
Expected: PASS, 2 passed

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/cycle_snapshot.py src/artifactsmmo_cli/ai/player.py tests/test_ai/test_cycle_snapshot_bank_gold.py
git commit -m "$(cat <<'EOF'
feat(tui): carry bank gold across the process boundary

CycleSnapshot carried the character's pocket gold and the bank's ITEMS,
and no bank gold — so the TUI render sites were not omitting the figure,
they had nothing to omit. Nullable and not defaulted to 0: an unread
balance must not claim an observation nobody made.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Ncwushdsr3ba3zkzgSrbsR
EOF
)"
```

---

### Task 6: The TUI shows both figures

**Files:**
- Modify: `src/artifactsmmo_cli/tui/widgets/status_pane.py:164`
- Modify: `src/artifactsmmo_cli/tui/screens/character_screen.py:24`
- Modify: `src/artifactsmmo_cli/tui/item_tables.py:29-35`
- Test: `tests/test_tui/test_item_tables.py` (append), `tests/test_tui/test_status_pane.py` (append), `tests/test_tui/test_character_screen.py` (append)

**Interfaces:**
- Consumes: Task 5's `CycleSnapshot.bank_gold`.
- Produces: nothing.

- [ ] **Step 1: Write the failing tests**

Each of the three modules already defines `_snap(**overrides)` and a render
helper — `_text(renderable)` in `test_item_tables.py` and
`test_character_screen.py`, `_render(pane)` in `test_status_pane.py`. Use them;
do not add new ones.

Append to `tests/test_tui/test_item_tables.py`:

```python
class TestBankGoldInHeader:
    """The bank's gold is account-wide — one balance every character shares —
    as against the per-character pocket the status pane shows."""

    def test_header_shows_bank_gold(self):
        out = _text(build_bank_items(_snap(bank_items={"copper_ore": 3},
                                           bank_gold=20_000)))
        assert "20,000 gold" in out

    def test_header_still_shows_the_item_count(self):
        out = _text(build_bank_items(_snap(bank_items={"copper_ore": 3, "ash_wood": 1},
                                           bank_gold=20_000)))
        assert "2 items" in out

    def test_unknown_bank_gold_renders_as_a_dash_not_zero(self):
        """A SYNCED bank whose gold was never read is unknown. Rendering 0 would
        claim an observation nobody made."""
        out = _text(build_bank_items(_snap(bank_items={"copper_ore": 3},
                                           bank_gold=None)))
        assert "— gold" in out
        assert "0 gold" not in out

    def test_unsynced_bank_keeps_its_own_placeholder(self):
        """bank_items is None is a different unknown from bank_gold is None."""
        assert "waiting for sync" in _text(build_bank_items(_snap(bank_items=None)))
```

Append to `tests/test_tui/test_status_pane.py`:

```python
class TestGoldLabel:
    def test_gold_row_is_labelled_carried(self):
        """Unqualified "Gold" repeated across five character panes reads as five
        separate balances. The bank's own figure lives in the bank pane."""
        pane = StatusPane()
        pane.update_snapshot(_snap(gold=8_016))
        assert "Gold (carried)" in _render(pane)

    def test_carried_gold_is_thousands_separated(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(gold=8_016))
        assert "8,016" in _render(pane)
```

Append to `tests/test_tui/test_character_screen.py`:

```python
class TestCharacterSheetGoldLabel:
    def test_gold_row_is_labelled_carried(self):
        assert "Gold (carried)" in _text(build_character_detail(_snap(gold=8_016)))

    def test_carried_gold_is_thousands_separated(self):
        assert "8,016" in _text(build_character_detail(_snap(gold=8_016)))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tui/test_item_tables.py tests/test_tui/test_status_pane.py tests/test_tui/test_character_screen.py -q --no-cov`
Expected: FAIL — `"20,000 gold" not in ...` and `"Gold (carried)" not in ...`

- [ ] **Step 3: Update the bank header**

In `src/artifactsmmo_cli/tui/item_tables.py`, replace `build_bank_items` with:

```python
def build_bank_items(snap: CycleSnapshot) -> RenderableType:
    """Bank header + qty/code table (qty-desc), or a waiting placeholder when
    the bank has not been synced yet (bank_items is None).

    The header carries the BANK's gold, which is account-wide — one balance every
    character shares — as against the per-character pocket the status pane and
    character sheet show. An unread balance renders as an em dash: a synced bank
    whose gold was never read is unknown, and 0 would be a claim.
    """
    if snap.bank_items is None:
        return Text("Bank — waiting for sync…")
    gold = "—" if snap.bank_gold is None else f"{snap.bank_gold:,}"
    header = Text(f"Bank  {len(snap.bank_items)} items · {gold} gold", style="bold")
    return Group(header, _item_table(snap.bank_items))
```

- [ ] **Step 4: Relabel the two pocket rows**

`src/artifactsmmo_cli/tui/widgets/status_pane.py:164` — replace:

```python
        t.add_row("Gold", str(s.gold))
```

with:

```python
        # "carried", because the bank holds an account-wide balance of its own
        # and an unqualified "Gold" on five character panes reads as five
        # separate totals. The bank figure lives in the bank pane's header.
        t.add_row("Gold (carried)", f"{s.gold:,}")
```

`src/artifactsmmo_cli/tui/screens/character_screen.py:24` — replace:

```python
    t.add_row("Gold", str(snap.gold))
```

with:

```python
    t.add_row("Gold (carried)", f"{snap.gold:,}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_tui/ -q --no-cov`
Expected: PASS, whole TUI suite

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/tui/ tests/test_tui/
git commit -m "$(cat <<'EOF'
feat(tui): distinguish carried gold from bank gold

The status pane and character sheet now say "Gold (carried)", and the
bank pane's header carries the account-wide balance next to its item
count. Unread bank gold renders as an em dash, never 0.

Gold is per-character and the bank is the account pool, so an unqualified
"Gold" row repeated across five character panes read as five separate
balances.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Ncwushdsr3ba3zkzgSrbsR
EOF
)"
```

---

### Task 7: Census reason, mutants, and the full gate

**Files:**
- Modify: `src/artifactsmmo_cli/audit/liveness_completeness.py:217`
- Modify: `formal/diff/mutate.py`
- Test: existing suites

**Interfaces:**
- Consumes: Tasks 1-6.
- Produces: nothing.

- [ ] **Step 1: Correct the dormancy reason**

`liveness_completeness.py:217` currently reads:

```python
    "DepositGoldAction": "conditional: gold is banked by DepositAll, not as a separate step",
```

The claim was false when written — `DepositAllAction.execute` called
`deposit_item` and nothing else. Task 3 made it true. Replace with:

```python
    # TRUE SINCE 2026-09-14, AND IT WAS NOT BEFORE. This reason shipped while
    # `DepositAllAction.execute` called `deposit_item` and nothing else, so it
    # excused the action with a mechanism that did not exist and no character
    # banked a coin in 184,010 cycles. `DepositAllAction._gold_deposit` now
    # issues the gold request on the same trip, which is why the action itself
    # stays dormant: the planner has no separate gold step to pick.
    "DepositGoldAction": "conditional: gold is banked inside DepositAllAction.execute, not as a separate planner step",
```

- [ ] **Step 2: Verify the census still passes**

Run: `uv run python scripts/gen_liveness.py --check`
Expected: "GATE CLEAN: 0 undeclared, 0 stale, 0 orphan declarations." and
"liveness alarms 0". Then restore the regenerated doc, which the gate rewrites
with live counts: `git checkout -- docs/behavioral_completeness/LIVENESS_MATRIX.md`

- [ ] **Step 3: Add the mutants**

In `formal/diff/mutate.py`, add a source constant beside the others near the top:

```python
GOLD_SURPLUS_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "gold_surplus_core.py"
```

and a group immediately before `BANK_EXPANSION_TIMING_MUTATIONS`:

```python
GOLD_SURPLUS_MUTATIONS = [
    # Bank every coin above the keep instead of whole chunks: the kept remainder
    # is what stops the live GAP-3 withdraw ferry re-triggering a deposit, so
    # this restores the Withdraw/DepositAll oscillation.
    ("gold_surplus: remainder banked too (deposit/withdraw trade one coin)",
     "    return max(0, (pocket - reserve) // chunk) * chunk",
     "    return max(0, pocket - reserve)"),
    # Drop the floor: a reserve above the pocket now banks a NEGATIVE chunk.
    ("gold_surplus: negative surplus not floored at zero",
     "    return max(0, (pocket - reserve) // chunk) * chunk",
     "    return ((pocket - reserve) // chunk) * chunk"),
    # Halve the chunk: banking becomes twice as eager and the slack the ferry
    # draws on halves with it.
    ("gold_surplus: chunk size halved",
     "GOLD_CHUNK = 10_000",
     "GOLD_CHUNK = 5_000"),
    # Hold nothing back for an imminent expansion: the pocket is banked below
    # `next_expansion_cost` and `expansion_fires` silently stops firing.
    ("gold_surplus: expansion hold neutered (expansion starves)",
     "    return next_expansion_cost",
     "    return 0"),
    # Treat an unread capacity as a fill ratio: UNKNOWN IS NOT FULL.
    ("gold_surplus: unknown bank capacity treated as known",
     "    if bank_capacity <= 0:\n        return 0",
     "    if False:\n        return 0"),
    # Strict inequality at the hold boundary: a bank exactly at the threshold
    # stops holding, which is the one fill where the runway begins.
    ("gold_surplus: hold boundary excludes the threshold itself",
     "    if bank_used * hold_den < bank_capacity * hold_num:",
     "    if bank_used * hold_den <= bank_capacity * hold_num:"),
]
```

Register it beside the other `run_group` calls, next to the deposit groups:

```python
    run_group(GOLD_SURPLUS_SRC, GOLD_SURPLUS_MUTATIONS,
              "tests/test_ai/test_gold_surplus_core.py", survivors)
```

- [ ] **Step 4: Check anchors resolve**

Run: `uv run python formal/diff/mutate.py --check-anchors`
Expected: "anchor check OK: N mutations, all anchors resolve uniquely". If any
anchor is STALE or ambiguous, fix the anchor text to match the file exactly —
a stale anchor silently masks a whole test module.

- [ ] **Step 5: Run the mutation subset**

`mutate.py` refuses to run with dirty target sources, so commit first:

```bash
git add src/artifactsmmo_cli/audit/liveness_completeness.py formal/diff/mutate.py
git commit -m "$(cat <<'EOF'
test(gold): mutants for the surplus core, and a dormancy reason that is now true

Six mutants: the remainder banked, the zero floor dropped, the chunk
halved, the expansion hold neutered, an unread capacity treated as known,
and the hold boundary made strict.

DepositGoldAction's census reason described a mechanism that did not
exist when it was written. Task 3 built it; the reason now names it.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Ncwushdsr3ba3zkzgSrbsR
EOF
)"
uv run python formal/diff/mutate.py --only gold_surplus_core.py
```

Expected: every mutant `killed:`, ending "mutation gate OK". A SURVIVOR means a
test is missing — add the test that fails under that mutant. Do not name a
specific test as the killer; find the one that actually fails.

- [ ] **Step 6: Full suite**

Run: `uv run pytest tests/ -q -n auto -p no:randomly`
Expected: all pass, "Required test coverage of 100% reached."

Two known-flaky failures are environmental, not yours — confirm they match
before dismissing either:
- `tests/test_ai/scenarios/test_held_task.py::test_the_open_task_is_cancelled_end_to_end_with_a_coin` — a wall-clock bomb under load; passes alone.
- `test_gear_taxonomy_live_audit` / `test_effect_coverage_audit_live` — `HTTP 429: rate limited` when the fleet is playing; pass alone.

- [ ] **Step 7: Full gate**

Run: `bash formal/gate.sh > /tmp/gate.log 2>&1; echo "rc=$?"; tail -5 /tmp/gate.log`
Expected: `rc=0`, "ALL GATE PARTS PASSED". Redirect rather than pipe —
`gate.sh | tail` reports tail's exit code, not the gate's.

Then: `git status --short`. The gate regenerates census docs; restore any it
rewrote rather than committing the churn.

- [ ] **Step 8: Verify runtime activation**

Green tests are not runtime activation. Confirm the new path actually fires:

```bash
uv run artifactsmmo plan Lor --learn
```

Lor held 28,016 gold on 2026-09-14 — the fattest purse in the fleet. Then check
the store after the fleet has restarted on this code:

```bash
sqlite3 ~/.cache/artifactsmmo/learning.db \
  "SELECT character, substr(ts,1,16) ts, gold, delta_gold
   FROM cycles WHERE action_class='DepositAllAction' AND delta_gold < -1000
   ORDER BY ts DESC LIMIT 10;"
```

Expected: rows with `delta_gold` at exact multiples of -10,000. **Zero rows
means the feature is inert** — the tests pass and nothing banks. Report that
rather than closing the task.

---

## Self-Review

**Spec coverage:**

| spec section | task |
|---|---|
| §4.1 pure core, `bankable_gold` | Task 1 |
| §4.1 hysteresis invariant | Task 1 (property), Task 4 (against the ferry) |
| §4.2 `_gold_deposit`, `apply`, `execute` | Task 3 |
| §4.2 `is_applicable` unchanged | Task 3 Step 1 (`test_is_applicable_still_ignores_gold`) |
| §4.3 `expansion_hold`, 70% threshold | Task 1, Task 2, Task 3 |
| §4.3 trigger is 75 not 95 | Task 2 Step 4 |
| §4.4 `CycleSnapshot.bank_gold` | Task 5 |
| §4.4 three render sites | Task 6 |
| §5 mutation guards | Task 7 Step 3 |
| §5 census reason reworded | Task 7 Step 1 |
| §5 full suite + gate note | Task 7 Steps 6-7 |
| §6 limitation | deferred by decision; no task |
| §7 out of scope | no task, intentionally |

No gaps.

**Placeholder scan:** No "TBD", "TODO", "similar to Task N", or "add appropriate
error handling". Two steps say "reuse whatever helper the existing module has"
(Task 6 Step 1) — that is a deliberate instruction to follow local convention in
a file the plan does not quote, not a missing detail; the assertion to write is
given verbatim in both cases.

**Type consistency:** `bankable_gold(pocket, reserve, chunk)` and
`expansion_hold(bank_used, bank_capacity, next_expansion_cost, hold_num,
hold_den)` are defined in Task 1 and called with those exact names in Task 3.
`HOLD_FILL_NUM`/`HOLD_FILL_DEN` are produced in Task 2 and consumed in Task 3.
`CycleSnapshot.bank_gold` is produced in Task 5 and consumed in Task 6.
`_gold_deposit` is defined once, in Task 3, and used by `apply` and `execute` in
the same task.

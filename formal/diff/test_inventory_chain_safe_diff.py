"""Differential test for `Formal.InventoryChainSafe` (REAL BUGS #7-#11).

Pin each of the four `Action.is_applicable` / `.apply` post-fixes against the
proved Lean chain_safe template, plus the TaskCancel coin-decrement contract:

* `WithdrawItemAction` (REAL BUG #7) — pre-fix `is_applicable` required only
  `inventory_free > 0` and `apply` minted `+quantity`, overflowing the cap
  when `quantity > inventory_free`. Probe: used=9, max=10, quantity=5 →
  used=14 > 10. Post-fix: `is_applicable` requires `inventory_free >= quantity`.
* `ClaimPendingItemAction` (REAL BUG #8) — no slot check; `apply` minted +1.
  Probe: full bag claim → used=11 > 10.
* `UnequipAction` (REAL BUG #9) — no slot check; `apply` pushed +1 into inv.
  Probe: full bag unequip → used=11 > 10.
* `TaskExchangeAction` (REAL BUG #10) — no slot check for reward grant.
  Probe: full bag exchange → server overrun. Post-fix: requires free >= 1.
* `TaskCancelAction` (REAL BUG #11) — server requires 1 task coin to cancel
  (HTTP 478) and the apply must decrement it. Pre-fix had neither.

Hypothesis (≥200 examples each) generates `(used, span, quantity)` tuples
including boundary cases. The four chain_safe actions agree with the Lean
oracle and the verified probe scenarios are pinned as regression tests.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.actions.claim import ClaimPendingItemAction
from artifactsmmo_cli.ai.actions.task_cancel import TaskCancelAction
from artifactsmmo_cli.ai.actions.task_exchange import TaskExchangeAction
from artifactsmmo_cli.ai.actions.unequip import UnequipAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState
from formal.diff.oracle_client import run_oracle


_GD = GameData()


def _mkstate(
    inventory: dict[str, int] | None = None,
    inventory_max: int = 10,
    equipment: dict[str, str | None] | None = None,
    bank_items: dict[str, int] | None = None,
    pending_items: tuple[tuple[str, str], ...] | None = None,
    task_code: str | None = None,
    task_total: int = 0,
) -> WorldState:
    return WorldState(
        character="probe", level=1, xp=0, max_xp=10, hp=10, max_hp=10, gold=0,
        skills={}, x=0, y=0,
        inventory=dict(inventory or {}),
        inventory_max=inventory_max,
        equipment=dict(equipment or {}),
        cooldown_expires=None,
        task_code=task_code, task_type=None,
        task_progress=0, task_total=task_total,
        bank_items=dict(bank_items or {}),
        bank_gold=0, pending_items=pending_items,
    )


# ─── Withdraw ────────────────────────────────────────────────────────────────


@settings(max_examples=200)
@given(
    used=st.integers(min_value=0, max_value=200),
    span=st.integers(min_value=0, max_value=200),
    quantity=st.integers(min_value=0, max_value=50),
    bank_qty=st.integers(min_value=0, max_value=200),
)
def test_withdraw_matches_lean(used, span, quantity, bank_qty):
    cap = used + span
    # `withdraw` requires accessible=True and a non-None bank_items dict.
    inv_filler = {"x": used} if used > 0 else {}
    state = _mkstate(inventory=inv_filler, inventory_max=cap,
                     bank_items={"alpha": bank_qty})
    a = WithdrawItemAction(code="alpha", quantity=quantity)
    py = a.is_applicable(state, _GD)
    lean = run_oracle("inventory_chain_safe", [[0, used, cap, quantity, bank_qty]])[0]
    assert py == lean["applicable"]
    assert lean["free"] == cap - used
    if py:
        # Proved invariant: passing check ⇒ quantity ≤ free ∧ quantity ≤ bank.
        assert quantity <= cap - used
        assert quantity <= bank_qty
        # Apply preserves the cap.
        post = a.apply(state, _GD)
        assert post.inventory_used <= post.inventory_max
        assert lean["post_used"] == used + quantity


def test_withdraw_regression_pin_used9_cap10_qty5_blocked():
    """REAL BUG #7 verified probe: used=9, cap=10, quantity=5 must be refused."""
    state = _mkstate(inventory={"x": 9}, inventory_max=10,
                     bank_items={"alpha": 100})
    a = WithdrawItemAction(code="alpha", quantity=5)
    assert a.is_applicable(state, _GD) is False
    lean = run_oracle("inventory_chain_safe", [[0, 9, 10, 5, 100]])[0]
    assert lean["applicable"] is False


def test_withdraw_boundary_quantity_equals_free_accepted():
    state = _mkstate(inventory={"x": 5}, inventory_max=10,
                     bank_items={"alpha": 100})
    a = WithdrawItemAction(code="alpha", quantity=5)
    assert a.is_applicable(state, _GD) is True
    post = a.apply(state, _GD)
    assert post.inventory_used == 10
    assert post.inventory_used <= post.inventory_max


# ─── Claim ───────────────────────────────────────────────────────────────────


@settings(max_examples=200)
@given(
    used=st.integers(min_value=0, max_value=200),
    span=st.integers(min_value=0, max_value=200),
    has_pending=st.booleans(),
)
def test_claim_matches_lean(used, span, has_pending):
    cap = used + span
    pending = (("p1", "alpha"),) if has_pending else None
    state = _mkstate(
        inventory={"x": used} if used > 0 else {},
        inventory_max=cap, pending_items=pending,
    )
    a = ClaimPendingItemAction()
    py = a.is_applicable(state, _GD)
    lean = run_oracle("inventory_chain_safe",
                      [[1, used, cap, 1 if has_pending else 0]])[0]
    assert py == lean["applicable"]
    if py:
        assert 1 <= cap - used
        post = a.apply(state, _GD)
        assert post.inventory_used <= post.inventory_max


def test_claim_regression_pin_full_bag_blocked():
    """REAL BUG #8 verified probe: full bag must refuse the claim."""
    state = _mkstate(inventory={"x": 10}, inventory_max=10,
                     pending_items=(("p1", "alpha"),))
    a = ClaimPendingItemAction()
    assert a.is_applicable(state, _GD) is False
    lean = run_oracle("inventory_chain_safe", [[1, 10, 10, 1]])[0]
    assert lean["applicable"] is False


def test_claim_boundary_one_free_slot_accepted():
    state = _mkstate(inventory={"x": 9}, inventory_max=10,
                     pending_items=(("p1", "alpha"),))
    a = ClaimPendingItemAction()
    assert a.is_applicable(state, _GD) is True
    post = a.apply(state, _GD)
    assert post.inventory_used == 10


# ─── Unequip ─────────────────────────────────────────────────────────────────


@settings(max_examples=200)
@given(
    used=st.integers(min_value=0, max_value=200),
    span=st.integers(min_value=0, max_value=200),
    slot_filled=st.booleans(),
)
def test_unequip_matches_lean(used, span, slot_filled):
    cap = used + span
    equipment = {"weapon_slot": "sword" if slot_filled else None}
    state = _mkstate(
        inventory={"x": used} if used > 0 else {},
        inventory_max=cap, equipment=equipment,
    )
    a = UnequipAction(slot="weapon_slot")
    py = a.is_applicable(state, _GD)
    lean = run_oracle("inventory_chain_safe",
                      [[2, used, cap, 1 if slot_filled else 0]])[0]
    assert py == lean["applicable"]
    if py:
        assert 1 <= cap - used
        post = a.apply(state, _GD)
        assert post.inventory_used <= post.inventory_max


def test_unequip_regression_pin_full_bag_blocked():
    """REAL BUG #9 verified probe: full bag unequip must refuse."""
    state = _mkstate(inventory={"x": 10}, inventory_max=10,
                     equipment={"weapon_slot": "sword"})
    a = UnequipAction(slot="weapon_slot")
    assert a.is_applicable(state, _GD) is False
    lean = run_oracle("inventory_chain_safe", [[2, 10, 10, 1]])[0]
    assert lean["applicable"] is False


def test_unequip_empty_slot_blocked():
    state = _mkstate(inventory_max=10, equipment={"weapon_slot": None})
    a = UnequipAction(slot="weapon_slot")
    assert a.is_applicable(state, _GD) is False
    lean = run_oracle("inventory_chain_safe", [[2, 0, 10, 0]])[0]
    assert lean["applicable"] is False


# ─── TaskExchange ────────────────────────────────────────────────────────────


@settings(max_examples=200)
@given(
    used=st.integers(min_value=0, max_value=200),
    span=st.integers(min_value=0, max_value=200),
    coins=st.integers(min_value=0, max_value=50),
    min_coins=st.integers(min_value=1, max_value=20),
)
def test_task_exchange_matches_lean(used, span, coins, min_coins):
    cap = used + span
    # Encode coins as part of inventory_used: the bag holds `coins` coin slots
    # plus `used` filler. We need used >= coins so the total slot count is `used`.
    if coins > used:
        return  # skip ill-formed combinations
    filler = used - coins
    inv = {}
    if coins > 0:
        inv[TASKS_COIN_CODE] = coins
    if filler > 0:
        inv["x"] = filler
    state = _mkstate(inventory=inv, inventory_max=cap)
    a = TaskExchangeAction(taskmaster_location=(1, 2), min_coins=min_coins)
    py = a.is_applicable(state, _GD)
    lean = run_oracle("inventory_chain_safe",
                      [[3, used, cap, coins, min_coins]])[0]
    assert py == lean["applicable"]
    if py:
        assert 1 <= cap - used
        assert min_coins <= coins
        post = a.apply(state, _GD)
        assert post.inventory_used <= post.inventory_max


def test_task_exchange_regression_pin_full_bag_blocked():
    """REAL BUG #10 verified probe: full bag exchange must refuse."""
    state = _mkstate(inventory={TASKS_COIN_CODE: 6, "x": 4}, inventory_max=10)
    a = TaskExchangeAction(taskmaster_location=(1, 2), min_coins=6)
    assert a.is_applicable(state, _GD) is False
    lean = run_oracle("inventory_chain_safe", [[3, 10, 10, 6, 6]])[0]
    assert lean["applicable"] is False


def test_task_exchange_boundary_one_free_slot_accepted():
    state = _mkstate(inventory={TASKS_COIN_CODE: 6, "x": 3}, inventory_max=10)
    a = TaskExchangeAction(taskmaster_location=(1, 2), min_coins=6)
    assert a.is_applicable(state, _GD) is True
    post = a.apply(state, _GD)
    assert post.inventory_used <= post.inventory_max


# ─── TaskCancel (coin handling) ──────────────────────────────────────────────


@settings(max_examples=200)
@given(
    coins=st.integers(min_value=0, max_value=20),
    has_task=st.booleans(),
)
def test_task_cancel_matches_lean(coins, has_task):
    inv = {TASKS_COIN_CODE: coins} if coins > 0 else {}
    state = _mkstate(
        inventory=inv,
        task_code="some_task" if has_task else None,
        task_total=10 if has_task else 0,
    )
    a = TaskCancelAction(taskmaster_location=(1, 2))
    py = a.is_applicable(state, _GD)
    lean = run_oracle("inventory_chain_safe",
                      [[4, coins, 1 if has_task else 0]])[0]
    assert py == lean["applicable"]
    if py:
        # Proved: under precondition, apply decrements coin by exactly 1.
        post = a.apply(state, _GD)
        assert post.inventory.get(TASKS_COIN_CODE, 0) == coins - 1
        assert lean["post_coins"] == coins - 1


def test_task_cancel_regression_pin_no_coin_blocked():
    """REAL BUG #11 verified probe: no coin ⇒ must refuse."""
    state = _mkstate(task_code="abc", task_total=10)
    a = TaskCancelAction(taskmaster_location=(1, 2))
    assert a.is_applicable(state, _GD) is False
    lean = run_oracle("inventory_chain_safe", [[4, 0, 1]])[0]
    assert lean["applicable"] is False


def test_task_cancel_apply_decrements_coin():
    state = _mkstate(inventory={TASKS_COIN_CODE: 1},
                     task_code="abc", task_total=10)
    a = TaskCancelAction(taskmaster_location=(1, 2))
    post = a.apply(state, _GD)
    assert TASKS_COIN_CODE not in post.inventory  # drops to 0 deleted
    assert post.task_code is None


def test_task_cancel_apply_decrements_coin_from_many():
    state = _mkstate(inventory={TASKS_COIN_CODE: 5},
                     task_code="abc", task_total=10)
    a = TaskCancelAction(taskmaster_location=(1, 2))
    post = a.apply(state, _GD)
    assert post.inventory[TASKS_COIN_CODE] == 4

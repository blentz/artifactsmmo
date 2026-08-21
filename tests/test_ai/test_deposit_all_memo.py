"""`DepositAllAction._deposits` is memoised on the state OBJECT, once.

The planner asks `is_applicable(state)` and then `apply(state)` with the same
state object and both need the deposit list, so every expanded node used to pay
for it twice. Profiled on C3P0's skill-gap search: 10,846 calls for 5,423 nodes,
11.7s of a 15.0s budget, all of it `select_bank_deposits` -> `bankable` ->
`reason_quantity`. The repeat is what is being removed — not the work itself.
"""

from dataclasses import replace

from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    gd._npc_stock = {"merchant": {"copper_ore": 5}}
    gd._monster_level = {"chicken": 1}
    return gd


def _action(gd: GameData) -> DepositAllAction:
    return DepositAllAction(bank_location=(1, 1), accessible=True, game_data=gd)


def test_the_same_state_object_is_computed_once(monkeypatch):
    """Two calls, one computation — the whole point."""
    gd = _gd()
    action = _action(gd)
    state = make_state(inventory={"copper_ore": 40}, inventory_max=50)
    calls = []
    import artifactsmmo_cli.ai.actions.deposit_all as mod
    real = mod.select_bank_deposits
    monkeypatch.setattr(mod, "select_bank_deposits",
                        lambda s, g, c: (calls.append(s), real(s, g, c))[1])
    first = action._deposits(state)
    second = action._deposits(state)
    assert len(calls) == 1
    assert first is second


def test_a_different_state_is_recomputed_even_when_equal(monkeypatch):
    """IDENTITY, NOT VALUE. An equal-but-distinct state recomputes rather than
    reusing — which is the conservative direction, and is what lets the memo skip
    hashing a 115-item bag. A value key that got equality subtly wrong would
    answer for the wrong state, which is worse than no memo at all."""
    gd = _gd()
    action = _action(gd)
    state = make_state(inventory={"copper_ore": 40}, inventory_max=50)
    twin = replace(state)
    calls = []
    import artifactsmmo_cli.ai.actions.deposit_all as mod
    real = mod.select_bank_deposits
    monkeypatch.setattr(mod, "select_bank_deposits",
                        lambda s, g, c: (calls.append(s), real(s, g, c))[1])
    assert action._deposits(state) == action._deposits(twin)
    assert len(calls) == 2


def test_a_changed_bag_gets_a_changed_answer():
    """The failure the memo must never cause: answering for a state the planner
    has already moved past. `apply` follows `is_applicable` on one state, then
    the NEXT node is a different object with a different bag."""
    gd = _gd()
    action = _action(gd)
    full = make_state(inventory={"copper_ore": 40}, inventory_max=50)
    assert action.is_applicable(full, gd) is True
    landed = action.apply(full, gd)
    # Everything surplus went to the bank, so there is nothing left to deposit.
    assert action._deposits(landed) != action._deposits(full)
    assert action.is_applicable(landed, gd) is False


def test_a_warm_memo_does_not_change_action_equality():
    """The planner dedups actions by value, so a warmed memo must not make two
    otherwise-identical actions compare different."""
    gd = _gd()
    warm, cold = _action(gd), _action(gd)
    warm._deposits(make_state(inventory={"copper_ore": 40}, inventory_max=50))
    assert warm._last_deposits is not None
    assert cold._last_deposits is None
    assert warm == cold

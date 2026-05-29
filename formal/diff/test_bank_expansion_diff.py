"""Differential test for `Formal.Phase8Invariants` Target B — bank-expansion
projection (REAL BUG #15, FIXED).

Pre-fix: `BuyBankExpansionAction.apply` only deducted gold; capacity was
read from `game_data._bank_capacity` (constant at planning time), so
`ExpandBankGoal.is_satisfied` could never flip False→True through projection.

Post-fix:
  * WorldState carries `bank_capacity: int | None`.
  * `apply` mints `state.bank_capacity = (state.bank_capacity or
    game_data._bank_capacity) + BANK_EXPANSION_SLOTS` and the goal reads
    `state.bank_capacity` first.

This test pins both the per-step contract (apply +20) and the projection
contract (chain flips the goal) against the Lean theorems
`bank_expansion_apply_increments_capacity` and
`bank_expansion_chain_reaches_satisfied`.
"""

from artifactsmmo_cli.ai.actions.bank_expansion import (
    BANK_EXPANSION_SLOTS,
    BuyBankExpansionAction,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
from artifactsmmo_cli.ai.world_state import WorldState


def _state(cap: int | None, items: int) -> WorldState:
    return WorldState(
        character="probe", level=1, xp=0, max_xp=10, hp=100, max_hp=100, gold=10000,
        skills={"mining": 1, "woodcutting": 1, "fishing": 1, "weaponcrafting": 1,
                "gearcrafting": 1, "jewelrycrafting": 1, "cooking": 1, "alchemy": 1},
        x=4, y=0,
        inventory={}, inventory_max=20,
        equipment={
            "weapon_slot": None, "rune_slot": None, "shield_slot": None,
            "helmet_slot": None, "body_armor_slot": None, "leg_armor_slot": None,
            "boots_slot": None, "ring1_slot": None, "ring2_slot": None,
            "amulet_slot": None, "artifact1_slot": None, "artifact2_slot": None,
            "artifact3_slot": None, "utility1_slot": None, "utility2_slot": None,
            "bag_slot": None,
        },
        cooldown_expires=None,
        task_code=None, task_type=None, task_progress=0, task_total=0,
        bank_items={f"item_{i}": 1 for i in range(items)},
        bank_gold=0, pending_items=None, bank_capacity=cap,
    )


def _gd(cap: int = 30, cost: int = 100) -> GameData:
    g = GameData()
    g._bank_capacity = cap
    g._next_expansion_cost = cost
    return g


def test_apply_increments_capacity_by_BANK_EXPANSION_SLOTS():
    """Lean role: bank_expansion_apply_increments_capacity."""
    action = BuyBankExpansionAction(bank_location=(4, 0), accessible=True)
    state = _state(cap=30, items=30)
    post = action.apply(state, _gd())
    assert post.bank_capacity == 30 + BANK_EXPANSION_SLOTS


def test_apply_chained_grows_capacity_linearly():
    """Lean role: buyBankExpansion_capacityN."""
    action = BuyBankExpansionAction(bank_location=(4, 0), accessible=True)
    state = _state(cap=30, items=30)
    gd = _gd()
    for _ in range(4):
        state = action.apply(state, gd)
    assert state.bank_capacity == 30 + 4 * BANK_EXPANSION_SLOTS


def test_chain_reaches_satisfied():
    """Lean role: bank_expansion_chain_reaches_satisfied.

    The BLOCKED counterexample (30/30, goal False) flips True after 1 apply
    (cap → 50, fill = 30/50 = 60% < 90%)."""
    action = BuyBankExpansionAction(bank_location=(4, 0), accessible=True)
    gd = _gd()
    goal = ExpandBankGoal(bank_accessible=True, game_data=gd)
    state = _state(cap=30, items=30)
    assert goal.is_satisfied(state) is False
    post = action.apply(state, gd)
    assert goal.is_satisfied(post) is True


def test_BANK_EXPANSION_SLOTS_matches_openapi_contract():
    """Source-of-truth pin: the OpenAPI contract for
    `POST /my/{name}/action/bank/buy_expansion` describes "Buy a 20 slots
    bank expansion." (openapi.json line 2843). The constant must match,
    otherwise the Lean Nat literal `BANK_EXPANSION_SLOTS := 20` and the
    Python constant drift apart."""
    assert BANK_EXPANSION_SLOTS == 20

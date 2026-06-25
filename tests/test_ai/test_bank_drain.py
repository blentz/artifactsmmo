"""Tests for over-cap bank-junk detection + DrainBankJunkGoal (idle bank drain)."""

from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.bank_drain import bank_drain_excess
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.drain_bank_junk import DrainBankJunkGoal
from artifactsmmo_cli.ai.strategy_driver import map_means
from artifactsmmo_cli.ai.tiers.means import MeansKind, _fires
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        # Far-skill-gated byproduct with no recipe use -> useful cap 0 (drain all).
        "sap": ItemStats(code="sap", level=1, type_="resource"),
        # Equippable craftable -> useful cap = EQUIPPABLE_KEEP (1) when not dominated.
        "copper_helmet": ItemStats(code="copper_helmet", level=1, type_="helmet",
                                   crafting_skill="gearcrafting", crafting_level=1),
        "copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                  crafting_skill="gearcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"copper_helmet": {"copper_bar": 6},
                            "copper_boots": {"copper_bar": 8}}
    gd._workshop_locations = {"gearcrafting": (2, 1)}
    gd._bank_location = (4, 0)
    return gd


def test_excess_drains_far_gated_bank_junk():
    """sap (no recipe use, useful cap 0) held only in the bank → drain all of it."""
    gd = _gd()
    state = make_state(level=5, bank_items={"sap": 50})
    assert bank_drain_excess(state, gd, protected_codes=frozenset()) == {"sap": 50}


def test_excess_keeps_useful_cap_in_bank():
    """An equippable (useful cap 1) is allowed to keep 1 in the bank; only the
    overflow above the cap is excess."""
    gd = _gd()
    state = make_state(level=5, bank_items={"copper_helmet": 5})
    assert bank_drain_excess(state, gd, protected_codes=frozenset()) == {"copper_helmet": 4}


def test_excess_credits_inventory_against_the_cap():
    """The cap bounds TOTAL holdings: inventory already holding toward the cap
    shrinks the bank allowance, so the whole bank stock becomes excess."""
    gd = _gd()
    state = make_state(level=5, inventory={"copper_helmet": 1},
                       bank_items={"copper_helmet": 5})
    assert bank_drain_excess(state, gd, protected_codes=frozenset()) == {"copper_helmet": 5}


def test_excess_excludes_committed_objective_gear():
    """Objective gear (protected) is never drained, even when over-cap in bank."""
    gd = _gd()
    state = make_state(level=5, bank_items={"copper_boots": 5})
    assert bank_drain_excess(state, gd,
                             protected_codes=frozenset({"copper_boots"})) == {}


def test_excess_empty_when_bank_unknown_or_within_cap():
    gd = _gd()
    assert bank_drain_excess(make_state(level=5), gd, frozenset()) == {}
    within = make_state(level=5, bank_items={"copper_helmet": 1})
    assert bank_drain_excess(within, gd, frozenset()) == {}


def test_goal_relevant_actions_withdraws_excess_sized_to_free_space():
    """DrainBankJunkGoal emits a WithdrawItemAction pulling the over-cap excess
    into the bag, sized to fit free slots."""
    gd = _gd()
    state = make_state(level=5, bank_items={"sap": 50}, inventory_max=200)
    goal = DrainBankJunkGoal(game_data=gd, protected_codes=frozenset(),
                             bank_accessible=True)
    actions = goal.relevant_actions([], state, gd)
    assert len(actions) == 1
    a = actions[0]
    assert isinstance(a, WithdrawItemAction)
    assert a.code == "sap"
    assert a.bank_location == (4, 0)
    assert 1 <= a.quantity <= 50
    assert a.is_applicable(state, gd)


def test_goal_relevant_actions_caps_quantity_at_free_slots():
    """Free slots smaller than the excess clamp the withdraw quantity."""
    gd = _gd()
    # inventory_max 10, 6 slots used -> 4 free; excess sap is 50 -> withdraw 4.
    state = make_state(level=5, inventory={"filler": 6},
                       bank_items={"sap": 50}, inventory_max=10)
    goal = DrainBankJunkGoal(game_data=gd, protected_codes=frozenset(),
                             bank_accessible=True)
    actions = goal.relevant_actions([], state, gd)
    assert len(actions) == 1
    assert actions[0].quantity == 4


def test_goal_no_actions_when_bank_location_unknown():
    gd = _gd()
    gd._bank_location = None
    state = make_state(level=5, bank_items={"sap": 50}, inventory_max=200)
    goal = DrainBankJunkGoal(game_data=gd, protected_codes=frozenset(),
                             bank_accessible=True)
    assert goal.relevant_actions([], state, gd) == []


def _ctx(**kw):
    from artifactsmmo_cli.ai.tiers.guards import SelectionContext
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
                gear_review_active=False)
    base.update(kw)
    return SelectionContext(**base)


def test_fires_on_idle_bank_junk_not_under_pressure_or_objective():
    gd = _gd()
    idle = make_state(level=5, bank_items={"sap": 50}, inventory_max=200)
    assert _fires(MeansKind.DRAIN_BANK_JUNK, idle, gd, None, _ctx()) is True
    # Under space pressure (>=0.85 full): no room to withdraw -> does NOT fire.
    pressured = make_state(level=5, inventory={"filler": 180},
                           bank_items={"sap": 50}, inventory_max=200)
    assert _fires(MeansKind.DRAIN_BANK_JUNK, pressured, gd, None, _ctx()) is False
    # The bank junk IS committed objective gear -> protected, does NOT fire.
    objective = make_state(level=5, bank_items={"copper_boots": 5}, inventory_max=200)
    assert _fires(MeansKind.DRAIN_BANK_JUNK, objective, gd, None,
                  _ctx(target_gear=frozenset({"copper_boots"}))) is False


def test_map_means_returns_drain_goal():
    g = map_means(MeansKind.DRAIN_BANK_JUNK, _gd(), _ctx(), make_state())
    assert isinstance(g, DrainBankJunkGoal)


def test_goal_satisfied_and_metadata():
    gd = _gd()
    empty = make_state(level=5, bank_items={"copper_helmet": 1})
    goal = DrainBankJunkGoal(game_data=gd, protected_codes=frozenset(),
                             bank_accessible=True)
    assert goal.is_satisfied(empty) is True
    assert goal.value(empty, gd) == 0.0
    surplus = make_state(level=5, bank_items={"sap": 50}, inventory_max=200)
    assert goal.is_satisfied(surplus) is False
    assert goal.value(surplus, gd) == 15.0
    assert goal.desired_state(surplus, gd) == {"bank_junk_drained": True}
    assert repr(goal) == "DrainBankJunk"

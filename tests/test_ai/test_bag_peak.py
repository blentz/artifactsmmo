"""`plan_bag_peak`: the most a committed plan holds in the bag."""

import dataclasses

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.deposit_item import DepositItemAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.bag_peak import plan_bag_peak
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._monster_drops = {"cow": [("cowhide", 1, 1, 1)]}
    gd._monster_locations = {"cow": [(1, 1)]}
    fill_monster_stat_defaults(gd)
    return gd


def test_the_peak_counts_the_bag_before_any_leg():
    state = make_state(inventory={"ore": 7, "gem": 1})
    assert plan_bag_peak([], state, _gd()) == (8, 2)


def test_the_replay_is_not_capped_at_the_bag():
    """Each `apply` saturates at `inventory_max`; the replay lifts the cap, so a
    50-unit withdraw into a 20-unit bag shows its real peak."""
    state = make_state(inventory={}, bank_items={"ore": 50}, inventory_max=20)
    withdraw = WithdrawItemAction(code="ore", quantity=50, bank_location=(0, 0))
    assert plan_bag_peak([withdraw], state, _gd()) == (50, 1)


def test_a_fight_to_a_drop_target_holds_the_target():
    """A fight leg repeats until its drop target is held: one kill's `apply`
    adds one cowhide, the leg's end holds four."""
    state = make_state(inventory={})
    fight = dataclasses.replace(FightAction(monster_code="cow", locations=frozenset({(1, 1)})),
                                drop_target=("cowhide", 4))
    assert plan_bag_peak([fight], state, _gd()) == (4, 1)
    plain = FightAction(monster_code="cow", locations=frozenset({(1, 1)}))
    assert plan_bag_peak([plain], state, _gd()) == (1, 1)


def test_the_peak_is_the_maximum_over_the_legs_not_the_end():
    state = make_state(inventory={}, bank_items={"ore": 9, "gem": 2})
    legs = [WithdrawItemAction(code="ore", quantity=9, bank_location=(0, 0)),
            WithdrawItemAction(code="gem", quantity=2, bank_location=(0, 0))]
    assert plan_bag_peak(legs, state, _gd()) == (11, 2)
    emptied = [*legs, DepositItemAction(code="ore", quantity=9, bank_location=(0, 0))]
    assert plan_bag_peak(emptied, state, _gd()) == (11, 2)

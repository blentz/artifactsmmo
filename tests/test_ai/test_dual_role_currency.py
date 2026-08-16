"""A dual-role item is one the character can WEAR and also SPEND."""
from artifactsmmo_cli.ai.dual_role_currency import dual_role_holdings, is_dual_role
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_dual_role_fixtures import medal_game_data


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

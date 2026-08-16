"""The fleet notices it is WEARING the trophy's price."""
from datetime import datetime, timezone

from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.learning.coordination_store import CoordinationStore
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_dual_role_fixtures import medal_game_data

NOW = datetime.now(timezone.utc)
"""Computed once at import time, not a fixed calendar stamp: `publish_holdings`
rows expire `DEMAND_TTL_SECONDS` after the `now` passed to it, so a hardcoded
past timestamp goes stale before `_resolve_turn_in`'s own `datetime.now(utc)`
read ever sees it."""


def _player_with(tmp_path, name):
    store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character=name)
    player = GamePlayer(character=name)
    player._coordination = store
    player.game_data = medal_game_data()
    return player, store


class _NoHolderStore:
    """A coordination stub whose `claim_turn_in` fails for a reason OTHER
    than a live incumbent (an IntegrityError race or a swallowed
    SQLAlchemyError — see `CoordinationStore.claim_turn_in`'s docstring),
    so `turn_in_holder` genuinely reports nobody. Exercises the branch a
    real two-character race can't reliably reproduce in a fast test."""

    def sibling_holdings(self, now):
        return {}

    def claim_turn_in(self, item_code, now):
        return False

    def turn_in_holder(self, item_code, now):
        return None


def test_turn_in_resolves_when_the_fleet_wears_enough(tmp_path):
    player, _store = _player_with(tmp_path, "Robby")
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
    # The buyer has nothing to surrender to itself.
    assert player._recall is None


def test_no_turn_in_one_medal_short(tmp_path):
    player, _store = _player_with(tmp_path, "Robby")
    CoordinationStore(db_path=str(tmp_path / "coord.db"),
                      character="HAL").publish_holdings({"lich_race_medal": 7}, NOW)
    state = make_state(level=27, inventory={}, bank_items={"lich_race_medal": 1},
                       equipment={"artifact1_slot": "lich_race_medal"})

    player._resolve_turn_in(state, player.game_data)

    assert player._turn_in is None
    assert player._recall is None


def test_a_character_below_the_item_level_does_not_claim_the_turn_in(tmp_path):
    """lich_race_trophy is level 20. A level-15 buyer would spend the fleet's
    medals on something it cannot wear."""
    player, _store = _player_with(tmp_path, "HAL")
    CoordinationStore(db_path=str(tmp_path / "coord.db"),
                      character="Robby").publish_holdings({"lich_race_medal": 9}, NOW)
    state = make_state(level=15, inventory={"lich_race_medal": 1})

    player._resolve_turn_in(state, player.game_data)

    assert player._turn_in is None
    assert player._recall is None


def test_upgrade_gate_blocks_a_purchase_the_picker_would_not_wear(tmp_path):
    """Even a fully-affordable, level-appropriate trophy is not bought if the
    character's own artifact slots are already better-occupied — rule 3."""
    player, _store = _player_with(tmp_path, "Robby")
    gd = player.game_data
    gd._item_stats["strong_relic"] = ItemStats(
        code="strong_relic", level=1, type_="artifact", hp_bonus=100)
    state = make_state(
        level=27, inventory={"lich_race_medal": 10},
        equipment={"artifact1_slot": "strong_relic", "artifact2_slot": "strong_relic",
                  "artifact3_slot": "strong_relic"})

    player._resolve_turn_in(state, gd)

    assert player._turn_in is None
    assert player._recall is None


def test_no_coordination_store_is_inert(tmp_path):
    """The common case (single-character `play <name>`, no `--all`): no
    crash, no turn-in, no recall."""
    player = GamePlayer(character="Robby")
    assert player._coordination is None
    gd = medal_game_data()
    state = make_state(level=27, inventory={"lich_race_medal": 20})

    player._resolve_turn_in(state, gd)

    assert player._turn_in is None
    assert player._recall is None


def test_a_losing_candidate_recalls_its_own_holdings_toward_the_winner(tmp_path):
    """Robby wins the claim using medals R2D2/C3P0/HAL published; when HAL
    later resolves for itself it must find Robby already holds the election
    and surrender exactly the medals the fleet needed from it."""
    db_path = str(tmp_path / "coord.db")
    for sibling, worn in (("R2D2", 3), ("C3P0", 3), ("HAL", 3)):
        CoordinationStore(db_path=db_path, character=sibling).publish_holdings(
            {"lich_race_medal": worn}, NOW)

    robby, _ = _player_with(tmp_path, "Robby")
    robby_state = make_state(level=27, inventory={}, bank_items={"lich_race_medal": 1})
    robby._resolve_turn_in(robby_state, robby.game_data)
    assert robby._turn_in is not None
    assert robby._turn_in.buyer == "Robby"

    hal, _ = _player_with(tmp_path, "HAL")
    hal_state = make_state(level=27, inventory={"lich_race_medal": 3},
                           bank_items={"lich_race_medal": 1})
    hal._resolve_turn_in(hal_state, hal.game_data)

    assert hal._turn_in is not None
    assert hal._turn_in.item_code == "lich_race_trophy"
    assert hal._turn_in.buyer == "Robby"
    assert hal._recall == ("lich_race_medal", 3)


def test_a_failed_claim_without_a_live_holder_reports_no_turn_in(tmp_path):
    player, _ = _player_with(tmp_path, "Robby")
    player._coordination = _NoHolderStore()
    state = make_state(level=27, inventory={"lich_race_medal": 20})

    player._resolve_turn_in(state, player.game_data)

    assert player._turn_in is None
    assert player._recall is None

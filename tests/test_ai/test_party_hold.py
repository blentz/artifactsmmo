"""The party hold: `HoldForPartyAction`, `JoinPartyGoal`, the `PARTY_JOIN`
guard's goal, and the player's party wiring (docs/PLAN_group_fights.md
increment 4)."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.api_action_error import ApiActionError
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.hold_for_party import HOLD_SECONDS, HoldForPartyAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.join_party import JOIN_PARTY_VALUE, JoinPartyGoal
from artifactsmmo_cli.ai.learning.coordination_store import CoordinationStore
from artifactsmmo_cli.ai.party_card import card_json
from artifactsmmo_cli.ai.party_lease_core import PartyLease
from artifactsmmo_cli.ai.player import PARTY_ASSEMBLY_SECONDS, GamePlayer
from artifactsmmo_cli.ai.strategy_driver import map_guard
from artifactsmmo_cli.ai.tiers.guards import GuardKind
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema, make_get_character_result
from tests.test_ai.test_strategy_driver import _ctx

LEASE = PartyLease("duskworm", "HAL", ("testchar",), "overworld", 3, -1)


def test_the_hold_moves_then_holds() -> None:
    hold = HoldForPartyAction(lease=LEASE)
    far = make_state(x=0, y=0)
    assert hold.is_applicable(far, GameData())
    assert not hold.is_applicable(replace(far, layer="underground"), GameData())
    planned = hold.apply(far, GameData())
    assert (planned.x, planned.y, planned.party_held) == (3, -1, "duskworm")
    assert hold.cost(far, GameData()) > hold.cost(planned, GameData()) == HOLD_SECONDS
    assert repr(hold) == "HoldForParty(duskworm)"


def test_executing_off_the_tile_moves() -> None:
    char = make_char_schema(x=3, y=-1)
    with patch("artifactsmmo_cli.ai.actions.movement.action_move", return_value=make_api_result(char)):
        moved = HoldForPartyAction(lease=LEASE).execute(make_state(x=0, y=0), MagicMock())
    assert (moved.x, moved.y) == (3, -1)


def test_executing_on_the_tile_holds_and_reads_the_character_back() -> None:
    """The leader's fight changes the member server-side: the hold reads it."""
    char = make_char_schema(x=3, y=-1, xp=777)
    with patch("artifactsmmo_cli.ai.actions.hold_for_party.time.sleep") as sleep, \
            patch("artifactsmmo_cli.ai.actions.hold_for_party.get_character",
                  return_value=make_get_character_result(char)):
        held = HoldForPartyAction(lease=LEASE).execute(make_state(x=3, y=-1), MagicMock())
    sleep.assert_called_once_with(HOLD_SECONDS)
    assert held.xp == 777


def test_a_failed_read_raises() -> None:
    with patch("artifactsmmo_cli.ai.actions.hold_for_party.time.sleep"), \
            patch("artifactsmmo_cli.ai.actions.hold_for_party.get_character", return_value=None):
        with pytest.raises(RuntimeError):
            HoldForPartyAction(lease=LEASE).execute(make_state(x=3, y=-1), MagicMock())


def test_the_goal_is_one_hold() -> None:
    gd = MagicMock()
    gd.region_of.return_value = "overworld"
    goal = JoinPartyGoal(LEASE, gd)
    state = make_state()
    assert not goal.is_satisfied(state) and goal.value(state, gd) == JOIN_PARTY_VALUE
    held = replace(state, party_held="duskworm")
    assert goal.is_satisfied(held) and goal.value(held, gd) == 0.0
    assert goal.desired_state(state, gd) == {"party_held": "duskworm"}
    (action,) = goal.relevant_actions([], state, gd)
    assert isinstance(action, HoldForPartyAction) and action.lease == LEASE
    assert repr(goal) == "JoinParty(duskworm)"


def test_the_guard_maps_to_the_join_goal() -> None:
    gd = MagicMock()
    assert isinstance(map_guard(GuardKind.PARTY_JOIN, gd, replace(_ctx(), party_hold=LEASE)),
                      JoinPartyGoal)
    with pytest.raises(ValueError, match="no lease"):
        map_guard(GuardKind.PARTY_JOIN, gd, _ctx())


T0 = datetime.now(tz=timezone.utc)


def _player(tmp_path: Path, name: str) -> tuple[GamePlayer, CoordinationStore]:
    store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character=name)
    player = GamePlayer(character=name)
    player.set_coordination_store(store)
    player.state = make_state(character=name, x=3, y=-1)
    player.game_data = GameData()
    return player, store


def test_without_a_store_there_is_no_party(tmp_path: Path) -> None:
    player = GamePlayer(character="hero")
    player.state = make_state(character="hero")
    player._refresh_party(T0)
    assert player._party_hold is None and player.state.party == ()
    fight = FightAction(monster_code="duskworm", locations=frozenset({(3, -1)}), participants=("Lor",))
    assert player._lead_party(fight) is fight


def test_the_roster_is_every_sibling_no_lease_names(tmp_path: Path) -> None:
    hal, hal_store = _player(tmp_path, "HAL")
    lor_store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="Lor")
    r2_store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="R2D2")
    c3_store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="C3P0")
    for store in (lor_store, r2_store, c3_store):
        store.publish_party_card(card_json(make_state(character=store.character, x=3, y=-1)), T0)
    assert c3_store.claim_party("lich", ("R2D2",), ("overworld", 0, 0), T0)
    hal._refresh_party(T0)
    assert [m.character for m in hal.state.party] == ["Lor"]
    # leading a lease: the party is its members
    assert hal_store.claim_party("duskworm", ("Lor",), ("overworld", 3, -1), T0)
    hal._refresh_party(T0)
    assert [m.character for m in hal.state.party] == ["Lor"] and hal._party_hold is None
    # a member: no party of its own, and the guard's lease
    lor, _ = _player(tmp_path, "Lor")
    lor._refresh_party(T0)
    assert lor.state.party == () and lor._party_hold == PartyLease(
        "duskworm", "HAL", ("Lor",), "overworld", 3, -1)


def test_the_leader_holds_until_the_party_is_assembled(tmp_path: Path) -> None:
    hal, _ = _player(tmp_path, "HAL")
    lor_store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="Lor")
    fight = FightAction(monster_code="duskworm", locations=frozenset({(3, -1)}), participants=("Lor",))
    # Lor is away: claim the lease, hold
    lor_store.publish_party_card(card_json(make_state(character="Lor", x=0, y=0)), T0)
    hal._refresh_party(T0)
    held = hal._lead_party(fight)
    assert isinstance(held, HoldForPartyAction) and held.lease.members == ("Lor",)
    assert lor_store.party_lease_for(T0) is not None
    # Lor on the tile, out of cooldown: fight
    lor_store.publish_party_card(card_json(make_state(character="Lor", x=3, y=-1)), T0)
    hal._refresh_party(T0)
    assert hal._lead_party(fight) is fight
    # a boss another leader holds: hold, no fight
    r2_store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="R2D2")
    assert r2_store.claim_party("lich", (), ("overworld", 0, 0), T0)
    lich = FightAction(monster_code="lich", locations=frozenset({(0, 0)}), participants=("Lor",))
    assert isinstance(hal._lead_party(lich), HoldForPartyAction)


def test_a_party_fight_releases_its_lease(tmp_path: Path) -> None:
    hal, _ = _player(tmp_path, "HAL")
    lor_store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="Lor")
    lor_store.publish_party_card(card_json(make_state(character="Lor", x=3, y=-1)), T0)
    hal._refresh_party(T0)
    fight = FightAction(monster_code="duskworm", locations=frozenset({(3, -1)}), participants=("Lor",))
    fight.execute = MagicMock(side_effect=RuntimeError("fight_lost: duskworm (turns=9)"))  # type: ignore[method-assign]
    with patch.object(hal, "_fetch_world_state", return_value=hal.state):
        hal._execute(fight, MagicMock())
    assert lor_store.party_lease_for(T0 + timedelta(seconds=1)) is None


def test_a_party_that_never_assembles_is_given_up(tmp_path: Path) -> None:
    """Past PARTY_ASSEMBLY_SECONDS the leader frees its members and blocks
    the party fight as a transport failure, so its plan moves on."""
    hal, _ = _player(tmp_path, "HAL")
    lor_store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="Lor")
    lor_store.publish_party_card(card_json(make_state(character="Lor", x=0, y=0)), T0)
    hal._refresh_party(T0)
    fight = FightAction(monster_code="duskworm", locations=frozenset({(3, -1)}), participants=("Lor",))
    assert isinstance(hal._lead_party(fight), HoldForPartyAction)
    assert fight.learning_key() not in hal._failure_blocks
    hal._party_since["duskworm"] = T0 - timedelta(seconds=PARTY_ASSEMBLY_SECONDS)
    assert isinstance(hal._lead_party(fight), HoldForPartyAction)
    assert fight.learning_key() in hal._failure_blocks
    assert "duskworm" not in hal._party_since
    assert lor_store.party_lease_for(datetime.now(tz=timezone.utc)) is None


def _assembled_leader(tmp_path: Path) -> tuple[GamePlayer, CoordinationStore, FightAction]:
    hal, _ = _player(tmp_path, "HAL")
    lor_store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="Lor")
    lor_store.publish_party_card(card_json(make_state(character="Lor", x=3, y=-1)), T0)
    hal._refresh_party(T0)
    fight = FightAction(monster_code="duskworm", locations=frozenset({(3, -1)}), participants=("Lor",))
    return hal, lor_store, fight


def test_a_refused_party_fight_keeps_its_lease(tmp_path: Path) -> None:
    """HTTP 499 (a member in cooldown) or 486 (off the tile) is no resolution:
    the members keep holding (live 2026-10-11: releasing on each refusal freed
    HAL between C3P0's 26 king_slime attempts)."""
    hal, lor_store, fight = _assembled_leader(tmp_path)
    fight.execute = MagicMock(side_effect=ApiActionError(499, "in cooldown"))  # type: ignore[method-assign]
    with patch.object(hal, "_fetch_world_state", return_value=hal.state):
        hal._execute(fight, MagicMock())
    assert lor_store.party_lease_for(datetime.now(tz=timezone.utc)) is not None


def test_a_won_party_fight_releases_its_lease(tmp_path: Path) -> None:
    hal, lor_store, fight = _assembled_leader(tmp_path)
    fight.execute = MagicMock(return_value=hal.state)  # type: ignore[method-assign]
    hal._execute(fight, MagicMock())
    assert lor_store.party_lease_for(datetime.now(tz=timezone.utc)) is None

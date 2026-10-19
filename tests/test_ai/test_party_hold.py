"""The party hold: `HoldForPartyAction`, `JoinPartyGoal`, the `PARTY_JOIN`
guard's goal, and the player's party wiring (docs/PLAN_group_fights.md
increment 4)."""

import dataclasses
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import artifactsmmo_cli.ai.gear_objective_context as ctx_mod
import artifactsmmo_cli.ai.player as player_mod
from artifactsmmo_cli.ai.actions.api_action_error import ApiActionError
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.hold_for_party import HOLD_SECONDS, HoldForPartyAction
from artifactsmmo_cli.ai.chosen_loadout import ChosenLoadout
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.join_party import JOIN_PARTY_VALUE, JoinPartyGoal
from artifactsmmo_cli.ai.learning.coordination_store import CoordinationStore
from artifactsmmo_cli.ai.party_card import card_json
from artifactsmmo_cli.ai.party_lease_core import PartyLease
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.player import PARTY_ASSEMBLY_SECONDS, GamePlayer
from artifactsmmo_cli.ai.scenario import load_bundle_game_data
from artifactsmmo_cli.ai.strategy_driver import map_guard
from artifactsmmo_cli.ai.tiers.guards import GuardKind
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema, make_get_character_result
from tests.test_ai.test_strategy_driver import _ctx

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")
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


def test_a_member_already_on_the_tile_still_plans_its_hold() -> None:
    """On the tile, the hold changes only `party_held`. With `party_held` out
    of the planner's state key the child collided with its parent in the
    visited set and was pruned (`explored=1 created=2 depth=0 plan_len=0`),
    so the guard had no plan and the commitment ran instead: live HAL,
    2026-10-12 05:15:29, back to `Gather(trout_spot)` with the lease live."""
    gd = GameData()
    goal = JoinPartyGoal(LEASE, gd)
    state = make_state(x=3, y=-1)
    plan = GOAPPlanner().plan(state, goal, goal.relevant_actions([], state, gd), gd)
    assert plan is not None and [repr(a) for a in plan] == ["HoldForParty(duskworm)"]


def test_a_member_on_another_layer_crosses_to_the_tile() -> None:
    """A member in the Abandoned House (`interior:-3,12`) called to an
    overworld boss tile plans the crossing, then the hold: the hold's
    `travel_region` is the tile's, so the search admits the region edges
    (`region_edges.admit_region_edges`)."""
    gd = load_bundle_game_data(BUNDLE)
    lease = PartyLease("king_slime", "C3P0", ("HAL",), "overworld", 3, -1)
    state = make_state(character="HAL", x=-3, y=12, layer="interior")
    goal = JoinPartyGoal(lease, gd)
    actions = build_actions(gd, state, None, bank_accessible=True, task_exchange_min_coins=0)
    plan = GOAPPlanner().plan(state, goal, actions, gd)
    assert [repr(a) for a in plan] == ["Transition((-3,12,interior)->(-3,12,overworld))",
                                       "HoldForParty(king_slime)"]


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
    assert hal._party_lease is not None and hal._party_lease.leader == "HAL"
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


def test_a_won_party_fight_keeps_its_lease(tmp_path: Path) -> None:
    """The leader fights the boss again: a released lease sent the member back
    to its own work between fights (live 2026-10-12, HAL to iron between two
    king_slime wins, then 13 refusals)."""
    hal, lor_store, fight = _assembled_leader(tmp_path)
    assert hal._lead_party(fight) is fight
    fight.execute = MagicMock(return_value=hal.state)  # type: ignore[method-assign]
    hal._execute(fight, MagicMock())
    assert lor_store.party_lease_for(datetime.now(tz=timezone.utc)) is not None


def test_a_lost_party_fight_releases_its_lease(tmp_path: Path) -> None:
    hal, lor_store, fight = _assembled_leader(tmp_path)
    fight.execute = MagicMock(side_effect=RuntimeError("fight_lost: duskworm (turns=9)"))  # type: ignore[method-assign]
    with patch.object(hal, "_fetch_world_state", return_value=hal.state):
        hal._execute(fight, MagicMock())
    assert lor_store.party_lease_for(datetime.now(tz=timezone.utc)) is None


def test_a_refused_party_fight_holds_one_cycle(tmp_path: Path) -> None:
    """After HTTP 499 the cards still read the party assembled (a member's card
    predates its cooldown): the leader holds one cycle instead of firing
    again, then fights."""
    hal, _, fight = _assembled_leader(tmp_path)
    assert hal._lead_party(fight) is fight
    fight.execute = MagicMock(side_effect=ApiActionError(499, "in cooldown"))  # type: ignore[method-assign]
    with patch.object(hal, "_fetch_world_state", return_value=hal.state):
        hal._execute(fight, MagicMock())
    assert isinstance(hal._lead_party(fight), HoldForPartyAction)
    assert hal._lead_party(fight) is fight


def test_a_new_commitment_ends_the_lease_it_leads(tmp_path: Path) -> None:
    """The leader's turn on the boss ended: its members are freed (live
    2026-10-12, HAL idle on the tile 5 minutes while C3P0 gathered shrimp).
    A lease another character leads is not this one's to end."""
    hal, lor_store, fight = _assembled_leader(tmp_path)
    hal._arbiter._committed_repr = "GatherMaterials(duskworm_scale)"
    hal._track_intention(None, hal.state, hal.state, True)
    assert hal._lead_party(fight) is fight
    # the same commitment, cycle after cycle: the lease stands
    hal._track_intention(None, hal.state, hal.state, True)
    assert lor_store.party_lease_for(datetime.now(tz=timezone.utc)) is not None
    hal._arbiter._committed_repr = "GatherMaterials(cooked_shrimp)"
    hal._track_intention(None, hal.state, hal.state, True)
    assert lor_store.party_lease_for(datetime.now(tz=timezone.utc)) is None
    # a member's commitment change leaves its leader's lease alone
    assert hal._lead_party(fight) is fight
    lor, _ = _player(tmp_path, "Lor")
    lor._arbiter._committed_repr = "GatherMaterials(sunflower)"
    lor._track_intention(None, lor.state, lor.state, True)
    assert lor_store.party_lease_for(datetime.now(tz=timezone.utc)) is not None
    # no store, nothing to end
    GamePlayer(character="solo")._release_led_party()


def test_the_party_card_is_published_from_the_given_state(tmp_path: Path) -> None:
    hal, _ = _player(tmp_path, "HAL")
    lor_store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="Lor")
    hal._publish_party_card(make_state(character="HAL", x=7, y=8))
    (card,) = lor_store.sibling_party_cards(datetime.now(tz=timezone.utc))
    assert '"x": 7' in card and '"y": 8' in card
    GamePlayer(character="solo")._publish_party_card(make_state())


def test_a_party_call_breaks_a_cached_plan_that_is_not_its_hold(tmp_path: Path) -> None:
    """Live 2026-10-11: HAL kept its cached sunflower batches through C3P0's
    lease. A call re-decides unless the cache IS the lease's hold."""
    lor, _ = _player(tmp_path, "Lor")
    seen: list[bool] = []

    def spy(*args: object) -> bool:
        seen.append(bool(args[-1]))
        return False

    lor._party_hold = PartyLease("duskworm", "HAL", ("Lor",), "overworld", 3, -1)
    cache = MagicMock(goal_repr="GatherMaterials(sunflower)")
    cache.selected_goal.is_satisfied.return_value = False
    lor._plan_cache = cache
    with patch("artifactsmmo_cli.ai.player.should_replan", side_effect=spy):
        lor._plan_or_reuse(lor.state, lor.game_data, [])
        cache.goal_repr = "JoinParty(duskworm)"
        lor._plan_or_reuse(lor.state, lor.game_data, [])
    assert seen == [True, False]


def test_a_lease_s_boss_and_loadout_are_the_fight_ahead(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Leader or member, the lease's boss is the fight its potions are stocked
    for, in the party loadout beside the other members' cards (residual R2)."""
    lor, _ = _player(tmp_path, "Lor")
    monkeypatch.setattr(ctx_mod, "farm_target", lambda *_: None)
    lor._draws_enabled = False
    assert lor._party_fight_loadout() is None
    seen: list[object] = []
    party = ChosenLoadout("duskworm", (("water_res_potion", 1),), (), ())

    def chosen(me, others, gd, monster, codes):  # type: ignore[no-untyped-def]
        seen.append(([o.character for o in others], monster, codes))
        return party

    monkeypatch.setattr(player_mod, "party_chosen_loadout", chosen)
    lor._party_lease = PartyLease("duskworm", "HAL", ("Lor", "R2D2"), "overworld", 3, -1,
                                  ("water_res_potion",))
    lor._party_cards = {"HAL": make_state(character="HAL"), "R2D2": make_state(character="R2D2")}
    ctx = lor._selection_context()
    assert ctx.fight_monster == "duskworm" and ctx.loadout == party
    assert seen[0] == (["HAL", "R2D2"], "duskworm", ("water_res_potion",))


def test_the_leader_fights_only_once_the_party_wears_its_loadout(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    hal, lor_store, fight = _assembled_leader(tmp_path)
    fight = dataclasses.replace(fight, party_loadout=("water_res_potion",))
    worn: list[list[str]] = []

    def wears(state, gd, codes):  # type: ignore[no-untyped-def]
        worn.append([state.character, *codes])
        return state.character != "Lor"

    monkeypatch.setattr(player_mod, "wears_party_loadout", wears)
    assert isinstance(hal._lead_party(fight), HoldForPartyAction)
    assert worn == [["HAL", "water_res_potion"], ["Lor", "water_res_potion"]]
    assert lor_store.party_lease_for(T0).loadout == ("water_res_potion",)
    monkeypatch.setattr(player_mod, "wears_party_loadout", lambda *a: True)
    assert hal._lead_party(fight) is fight

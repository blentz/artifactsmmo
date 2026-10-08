"""A live supply claim's batch is reserved from healing (USER 2026-10-08:
"Reserve the claimed batch"). Live, R2D2's RestoreHP cooked and ate the
cooked_rat_meat its SupplyBank claim produced, 4 of 4, 0 deposited."""

import dataclasses

from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.strategy_driver import map_guard
from artifactsmmo_cli.ai.tiers.guards import GuardKind
from tests.test_ai.fixtures import make_state

_STATS = {
    "cooked_rat_meat": ItemStats(code="cooked_rat_meat", level=25, type_="consumable", hp_restore=200),
    "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable", hp_restore=80),
}


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = dict(_STATS)
    gd._crafting_recipes = {"cooked_rat_meat": {"raw_rat_meat": 1},
                            "cooked_chicken": {"raw_chicken": 1}}
    return gd


def _pool() -> list:  # type: ignore[type-arg]
    return [RestAction(), UseConsumableAction(_item_stats=_STATS),
            CraftAction(code="cooked_rat_meat"), CraftAction(code="cooked_chicken")]


def test_unreserved_healing_keeps_every_food() -> None:
    kept = RestoreHPGoal().relevant_actions(_pool(), make_state(), _gd())
    assert len(kept) == 4


def test_the_claimed_batch_is_neither_cooked_nor_eaten() -> None:
    goal = RestoreHPGoal(reserved=frozenset({"cooked_rat_meat", "raw_rat_meat"}))
    kept = goal.relevant_actions(_pool(), make_state(), _gd())
    crafts = [a.code for a in kept if isinstance(a, CraftAction)]
    eat = next(a for a in kept if isinstance(a, UseConsumableAction))
    assert crafts == ["cooked_chicken"]
    assert set(eat._item_stats) == {"cooked_chicken"}
    assert any(isinstance(a, RestAction) for a in kept)


def test_a_craft_consuming_a_reserved_input_is_refused() -> None:
    goal = RestoreHPGoal(reserved=frozenset({"raw_chicken"}))
    kept = goal.relevant_actions(_pool(), make_state(), _gd())
    assert [a.code for a in kept if isinstance(a, CraftAction)] == ["cooked_rat_meat"]


def test_the_guard_passes_the_reservation() -> None:
    ctx = dataclasses.replace(NO_PROFILE_CONTEXT, supply_reserved=frozenset({"cooked_rat_meat"}))
    for kind in (GuardKind.HP_CRITICAL, GuardKind.REST_FOR_COMBAT):
        assert map_guard(kind, _gd(), ctx)._reserved == {"cooked_rat_meat"}


def test_the_player_reserves_its_claims_closure(monkeypatch) -> None:
    player = GamePlayer(character="hero")
    player.state = make_state()
    player.game_data = _gd()
    monkeypatch.setattr(player, "_winnable_farm_target", lambda: None)
    monkeypatch.setattr("artifactsmmo_cli.ai.player.pool_draw", lambda *a: (False, None))
    assert player._selection_context().supply_reserved == frozenset()
    player._supply_target = ("cooked_rat_meat", 10, 20)
    reserved = player._selection_context().supply_reserved
    assert {"cooked_rat_meat", "raw_rat_meat"} <= reserved


def test_the_claimed_target_itself_is_never_cooked() -> None:
    goal = RestoreHPGoal(reserved=frozenset({"cooked_rat_meat"}))
    kept = goal.relevant_actions(_pool(), make_state(), _gd())
    assert [a.code for a in kept if isinstance(a, CraftAction)] == ["cooked_chicken"]

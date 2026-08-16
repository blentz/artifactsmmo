"""Tests for the CURRENCY_TURNIN means: fires for the elected buyer AND for a
holder asked to surrender, inert for everyone else. Same shape as SUPPLY_BANK
(tests/test_ai/test_tiers_means.py) — this means is pure `ctx` plumbing, the
Task 5 decisions (`ctx.turn_in` / `ctx.recall`) threaded into the
collect-reward band."""

from artifactsmmo_cli.ai.currency_turnin import TurnIn
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.means import MeansKind, means_fires
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_dual_role_fixtures import medal_game_data


def _ctx(**kw) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None)
    base.update(kw)
    return SelectionContext(**base)


def _fires(kind: MeansKind, state, game_data, ctx: SelectionContext) -> bool:
    return means_fires(kind, state, game_data, None, ctx)


def test_turn_in_fires_for_the_elected_buyer():
    ctx = _ctx(turn_in=TurnIn(item_code="lich_race_trophy", npc_code="archaeologist",
                              price=10, currency="lich_race_medal",
                              buyer="Robby", fleet_total=10))
    assert _fires(MeansKind.CURRENCY_TURNIN, make_state(), medal_game_data(), ctx) is True


def test_turn_in_fires_for_a_holder_asked_to_surrender():
    ctx = _ctx(recall=("lich_race_medal", 2))
    assert _fires(MeansKind.CURRENCY_TURNIN, make_state(), medal_game_data(), ctx) is True


def test_turn_in_is_inert_for_an_uninvolved_character():
    assert _fires(MeansKind.CURRENCY_TURNIN, make_state(), medal_game_data(), _ctx()) is False

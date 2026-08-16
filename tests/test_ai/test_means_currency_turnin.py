"""Tests for the CURRENCY_TURNIN means: fires for the elected buyer AND for a
holder asked to surrender, inert for everyone else, and maps to the goal for
THIS character's role in the election. Same shape as SUPPLY_BANK
(tests/test_ai/test_tiers_means.py) — this means is pure `ctx` plumbing, the
Task 5 decisions (`ctx.turn_in` / `ctx.recall`) threaded into the
collect-reward band."""

from artifactsmmo_cli.ai.currency_turnin import TurnIn
from artifactsmmo_cli.ai.goals.currency_turnin import CurrencyTurnInGoal
from artifactsmmo_cli.ai.goals.surrender_currency import SurrenderCurrencyGoal
from artifactsmmo_cli.ai.strategy_driver import map_means
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.means import MeansKind, means_fires
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_dual_role_fixtures import medal_game_data

TROPHY = TurnIn(item_code="lich_race_trophy", npc_code="archaeologist",
                price=10, currency="lich_race_medal",
                buyer="Robby", fleet_total=10)


def _ctx(**kw) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None)
    base.update(kw)
    return SelectionContext(**base)


def _fires(kind: MeansKind, state, game_data, ctx: SelectionContext) -> bool:
    return means_fires(kind, state, game_data, None, ctx)


def test_turn_in_fires_for_the_elected_buyer():
    ctx = _ctx(turn_in=TROPHY)
    assert _fires(MeansKind.CURRENCY_TURNIN, make_state(), medal_game_data(), ctx) is True


def test_turn_in_fires_for_a_holder_asked_to_surrender():
    ctx = _ctx(recall=("lich_race_medal", 2))
    assert _fires(MeansKind.CURRENCY_TURNIN, make_state(), medal_game_data(), ctx) is True


def test_turn_in_is_inert_for_an_uninvolved_character():
    assert _fires(MeansKind.CURRENCY_TURNIN, make_state(), medal_game_data(), _ctx()) is False


def test_map_means_gives_the_buyer_goal_to_the_named_buyer():
    goal = map_means(MeansKind.CURRENCY_TURNIN, medal_game_data(), _ctx(turn_in=TROPHY),
                     make_state(character="Robby", level=27))
    assert isinstance(goal, CurrencyTurnInGoal)


def test_map_means_gives_a_non_buyer_the_surrender_goal_even_with_no_recall():
    """CRITICAL (fix-round-3): a SECOND buyer must be impossible.

    `_resolve_turn_in` sets `recall` only when the loser actually HOLDS units,
    so a level-20+ character that qualified, lost the claim, and holds ZERO
    units ends its cycle with `turn_in` set and `recall` None. Keying goal
    selection on "recall is None ⇒ I am the buyer" then handed that character
    `CurrencyTurnInGoal`, and it would withdraw a second full price and buy a
    SECOND trophy with the exclusive claim bypassed entirely — a double-spend
    of the fleet's currency. Identity is the only safe key: the buyer goal is
    for `turn_in.buyer == state.character` and nobody else."""
    goal = map_means(MeansKind.CURRENCY_TURNIN, medal_game_data(), _ctx(turn_in=TROPHY),
                     make_state(character="HAL", level=27))
    assert isinstance(goal, SurrenderCurrencyGoal)
    assert repr(goal) == "SurrenderCurrency(lich_race_medalx0)"


def test_map_means_gives_a_recalled_holder_the_surrender_goal():
    goal = map_means(MeansKind.CURRENCY_TURNIN, medal_game_data(),
                     _ctx(turn_in=TROPHY, recall=("lich_race_medal", 2)),
                     make_state(character="C3P0", level=17))
    assert isinstance(goal, SurrenderCurrencyGoal)
    assert repr(goal) == "SurrenderCurrency(lich_race_medalx2)"

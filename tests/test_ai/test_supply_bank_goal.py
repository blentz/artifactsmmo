"""Tests for SupplyBankGoal: is_satisfied reads BANKED quantity (not held),
desired_state targets the `banked` key, and value() is the clamped demand
lift shared with GrindCharacterXpGoal's construction.

The brief's test helper called a nonexistent `WorldState.create(...)` and a
`game_data` fixture not defined anywhere in `tests/test_ai/`. `WorldState` is
a plain frozen dataclass with no `create` classmethod (only
`from_character_schema`, which builds from a live API schema, not raw
kwargs) — the established direct-construction helper across this package is
`tests.test_ai.fixtures.make_state`, so `_state` below wraps that instead of
inventing a `create` API. `game_data` is a per-file fixture in this package
(see test_cancel_selection.py, test_obtain_sources.py), never a suite-wide
one, so it is defined locally here too.
"""

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.supply_bank import (
    SUPPLY_PRIORITY_CEILING,
    SUPPLY_PRIORITY_FLOOR,
    SupplyBankGoal,
)
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state


def _state(bank: dict[str, int] | None) -> WorldState:
    return make_state(bank_items=bank, bank_gold=0)


@pytest.fixture
def game_data() -> GameData:
    return GameData()


def test_unsatisfied_when_bank_lacks_the_target(game_data: GameData) -> None:
    goal = SupplyBankGoal(item_code="copper_bar", quantity=6, demand=6)
    assert goal.is_satisfied(_state({})) is False


def test_satisfied_when_bank_holds_the_target(game_data: GameData) -> None:
    goal = SupplyBankGoal(item_code="copper_bar", quantity=6, demand=6)
    assert goal.is_satisfied(_state({"copper_bar": 6})) is True


def test_satisfied_when_bank_holds_more_than_the_target(game_data: GameData) -> None:
    goal = SupplyBankGoal(item_code="copper_bar", quantity=6, demand=6)
    assert goal.is_satisfied(_state({"copper_bar": 9})) is True


def test_unvisited_bank_is_not_satisfied(game_data: GameData) -> None:
    goal = SupplyBankGoal(item_code="copper_bar", quantity=6, demand=6)
    assert goal.is_satisfied(_state(None)) is False


def test_desired_state_targets_banked_quantity(game_data: GameData) -> None:
    goal = SupplyBankGoal(item_code="copper_bar", quantity=6, demand=6)
    assert goal.desired_state(_state({}), game_data) == {"banked": {"copper_bar": 6}}


def test_priority_stays_inside_the_band(game_data: GameData) -> None:
    low = SupplyBankGoal(item_code="copper_bar", quantity=1, demand=0)
    high = SupplyBankGoal(item_code="copper_bar", quantity=1, demand=100_000)
    assert low.value(_state({}), game_data) == SUPPLY_PRIORITY_FLOOR
    assert high.value(_state({}), game_data) == SUPPLY_PRIORITY_CEILING


def test_priority_rises_with_demand(game_data: GameData) -> None:
    small = SupplyBankGoal(item_code="copper_bar", quantity=1, demand=2)
    large = SupplyBankGoal(item_code="copper_bar", quantity=1, demand=8)
    assert large.value(_state({}), game_data) > small.value(_state({}), game_data)


def test_ceiling_stays_below_the_survival_floor() -> None:
    assert SUPPLY_PRIORITY_CEILING < 70.0


def test_ceiling_stays_below_reach_skill_goal() -> None:
    assert SUPPLY_PRIORITY_CEILING < 55.0


def test_repr_shows_item_and_quantity() -> None:
    goal = SupplyBankGoal(item_code="copper_bar", quantity=6, demand=6)
    assert repr(goal) == "SupplyBank(copper_barx6)"

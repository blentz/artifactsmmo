"""Ruling T14e-perf: the dominance prune of `acquisition_cost._door_options`,
in isolation, so the mutant that removes it dies in seconds (the scenario
tests in `test_key_door_route.py` price every door route without it, which
takes minutes)."""

from fractions import Fraction

import pytest

from artifactsmmo_cli.ai import acquisition_cost
from artifactsmmo_cli.ai.acquisition_cost_core import RouteOption
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_model.gate import Gate, GateKind
from artifactsmmo_cli.ai.obtain_model.policy import DECOMPOSE_POLICY
from artifactsmmo_cli.ai.obtain_model.route import Route
from artifactsmmo_cli.ai.obtain_sources import UNBOUNDED_CAPACITY
from artifactsmmo_cli.ai.source_kind import SourceKind
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT, make_state

DOOR = (("vault_key", 1),)


class _PastADoor:
    """The one model read `_door_options` makes: a fight past `DOOR`."""

    def past_a_door(self, item: str, policy: object,
                    companions: object) -> tuple[tuple[Route, tuple[Gate, ...]], ...]:
        gate = Gate(GateKind.SPAWN_KNOWN, "warden", False, doors=(DOOR,))
        return ((Route(item, SourceKind.DROP, "warden", 1, UNBOUNDED_CAPACITY, (gate,)),
                 (gate,)),)


def _option(per_unit: int) -> RouteOption:
    return RouteOption(kind=SourceKind.DROP.value, venue="m", actions_per_application=Fraction(
        per_unit), yield_per=1, capacity=UNBOUNDED_CAPACITY)


@pytest.mark.parametrize(("ready", "door_route", "priced"), [(1, 2, False), (2, 2, False),
                                                            (3, 2, True)])
def test_a_door_route_a_ready_route_dominates_is_never_priced(
        monkeypatch: pytest.MonkeyPatch, ready: int, door_route: int, priced: bool) -> None:
    """A served route with no inputs, no unlock and unbounded capacity at no
    more per unit than the route past the door: the door is never priced (no
    `door_price` call) and the route is not offered. A dearer ready route
    leaves the door route to its price."""
    monkeypatch.setattr(acquisition_cost, "_priced", lambda *a: _option(door_route))
    calls: list[object] = []
    monkeypatch.setattr(acquisition_cost, "door_price", lambda door, *a: calls.append(door) or 1)
    monkeypatch.setattr(acquisition_cost, "door_toll", lambda door, s, g: ())
    out = acquisition_cost._door_options(
        "loot", make_state(), GameData(), TIMED_NO_PROFILE_CONTEXT, None,
        _PastADoor(), DECOMPOSE_POLICY, True, frozenset(), [_option(ready)])  # type: ignore[arg-type]
    assert (calls == [DOOR], len(out) == 1) == (priced, priced)

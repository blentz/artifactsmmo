"""disposal_route (Python) must agree with Formal.DisposalRoute.disposalRoute
(Lean) over the ENTIRE Bool³ domain.

The domain is finite (8 configurations), so the differential enumerates it
exhaustively — no sampling gap (lesson from the xpPositiveGate band-edge
mutant: random sampling can miss edges; here every "edge" is a case). Route
encoding matches the oracle: 0 = RECYCLE, 1 = DEPOSIT, 2 = DELETE. Any
reordering of the recycle/deposit arms, a dropped `bank_under_cap` guard, or an
inverted delete condition diverges from the proof on at least one of the 8.
"""
import itertools

import pytest

from artifactsmmo_cli.ai.disposal_route import Route, disposal_route
from formal.diff.oracle_client import run_oracle

_ROUTE_CODE = {Route.RECYCLE: 0, Route.DEPOSIT: 1, Route.DELETE: 2}

_ALL_CONFIGS = list(itertools.product([False, True], repeat=3))


@pytest.mark.parametrize(("recyclable", "bank_ok", "bank_under_cap"), _ALL_CONFIGS)
def test_route_matches_lean_exhaustively(recyclable, bank_ok, bank_under_cap):
    py_route = disposal_route(recyclable, bank_ok, bank_under_cap)
    lean = run_oracle("disposal_route", [
        [int(recyclable), int(bank_ok), int(bank_under_cap)]])[0]
    assert lean["route"] == _ROUTE_CODE[py_route]


def test_recycle_beats_open_bank():
    """Recycle wins even when deposit is also available — pins the arm order:
    a mutant that checks bank_ok first deposits recyclable gear instead of
    recovering its materials."""
    py = disposal_route(True, True, True)
    lean = run_oracle("disposal_route", [[1, 1, 1]])[0]
    assert py is Route.RECYCLE
    assert lean["route"] == 0


def test_bank_at_cap_deletes_despite_open_bank():
    """The anti-hoard guard: a code whose bank already holds every copy worth
    keeping deletes even at the bank — pins the dropped-`bank_under_cap` mutant
    that would bank the 703-sap pile forever."""
    py = disposal_route(False, True, False)
    lean = run_oracle("disposal_route", [[0, 1, 0]])[0]
    assert py is Route.DELETE
    assert lean["route"] == 2

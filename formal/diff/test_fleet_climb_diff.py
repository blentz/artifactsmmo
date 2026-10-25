"""Differential test: the Python fleet-climb core must agree with the proved
Lean `Formal.FleetClimb` (spec 2026-10-18 §2.5).

Two surfaces:

  * `amortized_climb_seconds` vs `amortized`: random non-negative rational
    climbs over 1..12 units, compared as exact fractions.
  * `climber` vs `pick`: up to 6 candidates in a random fleet order, each with
    a small rational remaining climb and a committed count (small ranges, so
    remaining ties, committed ties and full ties are all common). Python names
    the candidates by the stringified id; Lean reads the list in fleet order.
    Ids are a permutation, so the fleet order is never the id order — a name
    or id sort would diverge.
"""
from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.fleet_climb_core import amortized_climb_seconds, climber
from formal.diff.oracle_client import run_oracle

_rat = st.tuples(st.integers(min_value=0, max_value=40), st.integers(min_value=1, max_value=6))


@settings(max_examples=400, deadline=None)
@given(remaining=_rat, units=st.integers(min_value=1, max_value=12))
def test_amortized_matches_lean(remaining, units) -> None:
    num, den = remaining
    python = amortized_climb_seconds(Fraction(num, den), units)
    lean = run_oracle("fleet_climb_amortized", [[num, den, units]])[0]
    assert Fraction(lean["num"], lean["den"]) == python, (
        f"divergence: lean={lean} python={python} remaining={remaining} units={units}")


@st.composite
def _fleet(draw) -> list[tuple[int, tuple[int, int], int]]:
    n = draw(st.integers(min_value=1, max_value=6))
    ids = draw(st.permutations(list(range(n))))
    return [(ident,
             (draw(st.integers(min_value=0, max_value=3)), draw(st.integers(min_value=1, max_value=2))),
             draw(st.integers(min_value=0, max_value=2)))
            for ident in ids]


@settings(max_examples=400, deadline=None)
@given(fleet=_fleet())
def test_climber_matches_lean(fleet) -> None:
    order = tuple(str(ident) for ident, _, _ in fleet)
    remaining = {str(ident): Fraction(*rem) for ident, rem, _ in fleet}
    committed = {str(ident): com for ident, _, com in fleet}
    python = int(climber(remaining, committed, order))
    args = [len(fleet)]
    for ident, (num, den), com in fleet:
        args.extend([ident, num, den, com])
    lean = run_oracle("fleet_climb_pick", [args])[0]["pick"]
    assert lean == python, f"divergence: lean={lean} python={python} fleet={fleet}"


def test_spec_tie_goes_to_fewer_committed_then_fleet_order() -> None:
    """Pin §2.5's tie rule on both sides: 1 and 2 tie on remaining 7, 2 has
    less committed work; then a full tie between 5 and 3 goes to 5, first in
    fleet order though not first by id."""
    assert run_oracle("fleet_climb_pick", [[3, 0, 9, 1, 0, 1, 7, 1, 2, 2, 7, 1, 0]])[0] == {"pick": 2}
    assert climber({"0": Fraction(9), "1": Fraction(7), "2": Fraction(7)},
                   {"0": 0, "1": 2, "2": 0}, ("0", "1", "2")) == "2"
    assert run_oracle("fleet_climb_pick", [[2, 5, 7, 1, 0, 3, 7, 1, 0]])[0] == {"pick": 5}
    assert climber({"5": Fraction(7), "3": Fraction(7)}, {"5": 0, "3": 0}, ("5", "3")) == "5"

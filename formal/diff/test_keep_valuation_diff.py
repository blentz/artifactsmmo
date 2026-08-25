"""bank_surplus_pure / drain_licensed_pure / bank_under_cap_pure (Python) must
agree with Formal.DisposalRoute.bankSurplus / drainLicensed / bankUnderCap
(Lean) over an int grid.

These three are the ONE quantity-typed "worth keeping" valuation that
`ai/bank_drain` and `ai/disposal_route` both read. The differential asserts all
three together on every example, because it is their MUTUAL CONSISTENCY that
carries the anti-livelock invariant `drained > 0 ⇒ route ≠ DEPOSIT`: a mutation
that shifts one of them off the shared `bankSurplus` (an off-by-one in the
drain's bound, a `<` flipped to `<=` in the deposit gate) reintroduces the
withdraw↔redeposit cycle without changing either function's own signature.

The grid straddles `keep == bank_qty` — the boundary where the surplus is
exactly 0 and the two gates must BOTH decline (nothing to drain, nothing more
worth banking).
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.keep_valuation import (
    bank_surplus_pure,
    bank_under_cap_pure,
    drain_licensed_pure,
)
from formal.diff.oracle_client import run_oracle

_qty = st.integers(min_value=-20, max_value=20)


@settings(max_examples=600)
@given(destroyable=_qty, keep=_qty, bank_qty=_qty)
def test_valuation_matches_lean(destroyable, keep, bank_qty):
    lean = run_oracle("keep_valuation", [[destroyable, keep, bank_qty]])[0]
    assert lean["surplus"] == bank_surplus_pure(keep, bank_qty)
    assert lean["licensed"] == drain_licensed_pure(destroyable, keep, bank_qty)
    assert lean["under_cap"] == int(bank_under_cap_pure(keep, bank_qty))


def test_exactly_at_cap_neither_drains_nor_deposits():
    """The boundary: bank holds exactly the keep quantity. Surplus 0 — the drain
    licenses nothing, and the route must NOT deposit (there is no room left that
    is worth keeping). A `<= 0` deposit gate would bank forever here."""
    lean = run_oracle("keep_valuation", [[99, 7, 7]])[0]
    assert lean["surplus"] == bank_surplus_pure(7, 7) == 0
    assert lean["licensed"] == drain_licensed_pure(99, 7, 7) == 0
    assert lean["under_cap"] == 0
    assert bank_under_cap_pure(7, 7) is False


def test_the_live_sap_pile_drains_and_never_deposits():
    """704 banked sap against a keep of 1 — the pile this epic came from. The
    drain licenses 703 AND the deposit gate is closed, on both sides."""
    lean = run_oracle("keep_valuation", [[704, 1, 704]])[0]
    assert lean["licensed"] == drain_licensed_pure(704, 1, 704) == 703
    assert lean["under_cap"] == 0
    assert bank_under_cap_pure(1, 704) is False


def test_under_cap_material_is_deposit_eligible_and_undrainable():
    """The complement (no-over-shedding): 130 banked iron_ore against a keep of
    400 — a reachable consumer's full demand. Nothing drains, DEPOSIT is open."""
    lean = run_oracle("keep_valuation", [[130, 400, 130]])[0]
    assert lean["licensed"] == drain_licensed_pure(130, 400, 130) == -270
    assert lean["under_cap"] == 1
    assert bank_under_cap_pure(400, 130) is True


def test_ownership_licence_bounds_the_drain():
    """`destroyable` (the keep authority's ownership cap) is a hard ceiling on the
    surplus: 18 banked axes with a keep of 0 are all surplus, but only 17 may
    ever leave. Pins the min-arm-drop mutation."""
    lean = run_oracle("keep_valuation", [[17, 0, 18]])[0]
    assert lean["surplus"] == bank_surplus_pure(0, 18) == 18
    assert lean["licensed"] == drain_licensed_pure(17, 0, 18) == 17

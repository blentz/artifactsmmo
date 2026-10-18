"""Differential test: the Python gear-objective core must agree with the proved
Lean `Formal.GearObjective` (spec 2026-10-18 §2.3, §2.4).

Two surfaces:

  * `achievable_layers` vs `layers`: Hypothesis draws catalogues of up to 6
    items. Each item carries a base flag and a list of ALTERNATIVE requirement
    bitmasks; an item is unlocked by a union that holds every item of some
    alternative (an empty mask unlocks it from the start). That is the general
    form of a monotone `unlock` over the catalogue (a monotone Boolean function
    is an OR of ANDs), and it keeps its input, as the Python core demands.
    Items travel as list indices; the Python side names them by the stringified
    index, and layers are compared as sorted id lists.
  * `piece_order_key` vs `pieceKey`/`pieceOrder`: random pieces with a layer,
    rational gain (zero and negative allowed), positive rational price and a
    slot rank. Python sorts the indices by key with stable `sorted`; Lean sorts
    with stable `List.mergeSort` — equal keys must keep input order on both.
"""
from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.gear_objective_core import achievable_layers, piece_order_key
from formal.diff.oracle_client import run_oracle

_MAX_ITEMS = 6


@st.composite
def _catalogue(draw) -> list[tuple[bool, list[int]]]:
    n = draw(st.integers(min_value=0, max_value=_MAX_ITEMS))
    mask = st.integers(min_value=0, max_value=(1 << n) - 1)
    return [(draw(st.booleans()), draw(st.lists(mask, max_size=3))) for _ in range(n)]


def _python_layers(catalogue: list[tuple[bool, list[int]]]) -> list[list[int]]:
    n = len(catalogue)
    base = frozenset(str(i) for i, (flag, _) in enumerate(catalogue) if flag)

    def unlock(held: frozenset[str]) -> frozenset[str]:
        opened = {
            str(i) for i, (_, alts) in enumerate(catalogue)
            if any(all(str(b) in held for b in range(n) if m >> b & 1) for m in alts)
        }
        return held | opened

    return [sorted(int(code) for code in layer) for layer in achievable_layers(base, unlock)]


@settings(max_examples=400, deadline=None)
@given(catalogue=_catalogue())
def test_layers_match_lean(catalogue) -> None:
    args = [len(catalogue)]
    for flag, alts in catalogue:
        args.extend([int(flag), len(alts), *alts])
    lean = run_oracle("gear_objective_layers", [args])[0]["layers"]
    python = _python_layers(catalogue)
    assert lean == python, f"divergence: lean={lean} python={python} catalogue={catalogue}"


_ratio = st.tuples(st.integers(min_value=-3, max_value=12), st.integers(min_value=1, max_value=4))
_piece = st.tuples(
    st.integers(min_value=0, max_value=3),                                      # layer
    _ratio,                                                                     # gain num/den
    st.tuples(st.integers(min_value=1, max_value=9), st.integers(min_value=1, max_value=4)),  # price > 0
    st.integers(min_value=0, max_value=3),                                      # slot rank
)


@settings(max_examples=400, deadline=None)
@given(pieces=st.lists(_piece, max_size=6))
def test_piece_order_matches_lean(pieces) -> None:
    keys = [piece_order_key(layer, Fraction(*gain), Fraction(*price), rank)
            for layer, gain, price, rank in pieces]
    python = sorted(range(len(pieces)), key=lambda i: keys[i])
    args = [len(pieces)]
    for layer, (gn, gd), (pn, pd), rank in pieces:
        args.extend([layer, gn, gd, pn, pd, rank])
    lean = run_oracle("gear_objective_order", [args])[0]["order"]
    assert lean == python, f"divergence: lean={lean} python={python} pieces={pieces}"


def test_spec_two_layer_chain_matches_lean() -> None:
    """Pin the §2.3 shape: item 0 is free, item 1 needs 0, item 2 needs 1."""
    catalogue = [(True, []), (False, [0b001]), (False, [0b010])]
    assert _python_layers(catalogue) == [[0], [1], [2]]
    args = [3, 1, 0, 0, 1, 0b001, 0, 1, 0b010]
    assert run_oracle("gear_objective_layers", [args])[0]["layers"] == [[0], [1], [2]]

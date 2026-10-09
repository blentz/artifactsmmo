"""Differential tests for consumable utility increment 3: the live
`ai/loop_rate_core.recovery_seconds` / `xp_per_second` must agree with the proved
`Formal.LoopRate.recovery` / `xpRate`.

The Lean model works on ONE common scale: every price and the eat cooldown are
passed multiplied by the lcm of their denominators, and the Lean recovery is
that scale times the Python `Fraction` (a minimum of sums is homogeneous).
Inputs stay small because the Lean recovery is the plain recursion over count
vectors (no memo): ≤ 3 foods, restores ≥ 6 and ≤ 160 HP missing."""

from fractions import Fraction
from math import lcm

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.loop_rate_core import recovery_seconds, xp_per_second
from formal.diff.oracle_client import run_oracle

_price = st.fractions(min_value=0, max_value=60, max_denominator=12)
_food = st.tuples(st.integers(min_value=6, max_value=120), _price)
_recovery_case = st.tuples(
    st.integers(min_value=-3, max_value=160),                   # missing
    st.integers(min_value=1, max_value=400),                    # max hp
    st.lists(_food, max_size=3),
    st.one_of(st.just(Fraction(3)), _price),                    # eat seconds
)


def _scale(values: list[Fraction]) -> int:
    return lcm(1, *(v.denominator for v in values))


def _recovery_args(missing: int, max_hp: int, food: list[tuple[int, Fraction]],
                   eat: Fraction) -> tuple[int, list[int]]:
    scale = _scale([eat, *(p for _, p in food)])
    args = [scale, int(eat * scale), max_hp, max(0, missing), len(food)]
    for restore, price in food:
        args += [restore, int(price * scale)]
    return scale, args


@settings(max_examples=200, deadline=None)
@given(cases=st.lists(_recovery_case, min_size=1, max_size=20))
def test_recovery_matches_lean(cases: list[tuple[int, int, list[tuple[int, Fraction]], Fraction]]) -> None:
    built = [_recovery_args(*case) for case in cases]
    rows = run_oracle("loop_recovery", [args for _, args in built])
    for case, (scale, _), row in zip(cases, built, rows, strict=True):
        assert recovery_seconds(*case) == Fraction(row["recovery"], scale), case


def test_recovery_witnesses_against_lean() -> None:
    """The Lean file's witnesses, through the oracle and the live code."""
    cases = [
        (60, 100, [], Fraction(3)),
        (60, 100, [(50, Fraction(0))], Fraction(3)),
        (60, 100, [(50, Fraction(40))], Fraction(3)),
        (60, 100, [(50, Fraction(60))], Fraction(3)),
        (0, 100, [(50, Fraction(0))], Fraction(3)),
        (1, 100, [], Fraction(3)),
        (250, 100, [], Fraction(3)),
    ]
    expected = [60, 3, 53, 60, 0, 3, 100]
    built = [_recovery_args(*case) for case in cases]
    rows = run_oracle("loop_recovery", [args for _, args in built])
    assert [Fraction(row["recovery"], scale) for (scale, _), row in zip(built, rows, strict=True)] == expected
    assert [recovery_seconds(*case) for case in cases] == expected


_seconds = st.fractions(min_value=0, max_value=300, max_denominator=20)
_xp_case = st.tuples(
    st.integers(min_value=0, max_value=5000),
    st.fractions(min_value=Fraction(1, 20), max_value=120, max_denominator=20),
    _seconds, _seconds,
)


@settings(max_examples=300, deadline=None)
@given(cases=st.lists(_xp_case, min_size=1, max_size=30))
def test_xp_rate_matches_lean(cases: list[tuple[int, Fraction, Fraction, Fraction]]) -> None:
    args = []
    scales = []
    for xp, fight, recovery, consumed in cases:
        scale = _scale([fight, recovery, consumed])
        scales.append(scale)
        args.append([xp, scale, int(fight * scale), int(recovery * scale), int(consumed * scale)])
    rows = run_oracle("loop_xp_rate", args)
    for case, row in zip(cases, rows, strict=True):
        assert xp_per_second(*case) == Fraction(row["num"], row["den"]), case

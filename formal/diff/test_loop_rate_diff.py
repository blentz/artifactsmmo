"""Differential tests for consumable utility increments 3-4: the live
`ai/loop_rate_core.recovery_choice` / `consumed_seconds` / `xp_per_second` must
agree with the proved `Formal.LoopRate.recovery` / `planCost` / `consumedPrice` /
`xpRate`. The chosen count vector must COST the proved minimum (`planCost` of
it equals `recovery`), so the counts the floor reads are an optimal plan.

The Lean model works on ONE common scale: every price and the eat cooldown are
passed multiplied by the lcm of their denominators, and the Lean recovery is
that scale times the Python `Fraction` (a minimum of sums is homogeneous).
Inputs stay small because the Lean recovery is the plain recursion over count
vectors (no memo): ≤ 3 foods, restores ≥ 6 and ≤ 160 HP missing."""

from fractions import Fraction
from math import lcm

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.loop_rate_core import (
    Food,
    consumed_seconds,
    recovery_choice,
    recovery_seconds,
    xp_per_second,
)
from formal.diff.oracle_client import run_oracle

_price = st.fractions(min_value=0, max_value=60, max_denominator=12)
_food = st.tuples(st.integers(min_value=6, max_value=120), st.one_of(st.none(), _price),
                  st.integers(min_value=0, max_value=4))
_recovery_case = st.tuples(
    st.integers(min_value=-3, max_value=160),                   # missing
    st.integers(min_value=1, max_value=400),                    # max hp
    st.lists(_food, max_size=3),
    st.one_of(st.just(Fraction(3)), _price),                    # eat seconds
)


def _scale(values: list[Fraction]) -> int:
    return lcm(1, *(v.denominator for v in values))


def _recovery_args(missing: int, max_hp: int, food: list[Food],
                   eat: Fraction) -> tuple[int, list[int]]:
    scale = _scale([eat, *(p for _, p, _ in food if p is not None)])
    args = [scale, int(eat * scale), max_hp, max(0, missing), len(food)]
    for restore, price, held in food:
        args += [restore, 0 if price is None else 1, 0 if price is None else int(price * scale), held]
    return scale, args


@settings(max_examples=200, deadline=None)
@given(cases=st.lists(_recovery_case, min_size=1, max_size=20))
def test_recovery_matches_lean(cases: list[tuple[int, int, list[Food], Fraction]]) -> None:
    built = [_recovery_args(*case) for case in cases]
    rows = run_oracle("loop_recovery", [args for _, args in built])
    choices = [recovery_choice(*case) for case in cases]
    costs = run_oracle("loop_plan_cost", [args + list(counts)
                                          for (_, args), (_, counts) in zip(built, choices, strict=True)])
    for case, (scale, _), row, (value, _), cost in zip(cases, built, rows, choices, costs, strict=True):
        assert value == Fraction(row["recovery"], scale), case
        assert recovery_seconds(*case) == value, case
        assert Fraction(cost["cost"], scale) == value, case


def test_recovery_witnesses_against_lean() -> None:
    """The Lean file's witnesses, through the oracle and the live code."""
    cases: list[tuple[int, int, list[Food], Fraction]] = [
        (60, 100, [], Fraction(3)),
        (60, 100, [(50, Fraction(0), 0)], Fraction(3)),
        (60, 100, [(50, Fraction(40), 0)], Fraction(3)),
        (60, 100, [(50, Fraction(60), 0)], Fraction(3)),
        (60, 100, [(50, Fraction(60), 2)], Fraction(3)),
        (60, 100, [(50, None, 1)], Fraction(3)),
        (0, 100, [(50, Fraction(0), 0)], Fraction(3)),
        (1, 100, [], Fraction(3)),
        (250, 100, [], Fraction(3)),
    ]
    expected = [60, 3, 53, 60, 3, 13, 0, 3, 100]
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


_potion = st.tuples(st.integers(min_value=0, max_value=8), st.one_of(st.none(), _price),
                    st.integers(min_value=0, max_value=8))


@settings(max_examples=300, deadline=None)
@given(cases=st.lists(st.lists(_potion, max_size=3), min_size=1, max_size=30))
def test_consumed_matches_lean(cases: list[list[tuple[int, Fraction | None, int]]]) -> None:
    args = []
    scales = []
    for potions in cases:
        scale = _scale([p for _, p, _ in potions if p is not None])
        scales.append(scale)
        row = [len(potions)]
        for used, price, held in potions:
            row += [used, 0 if price is None else 1, 0 if price is None else int(price * scale), held]
        args.append(row)
    rows = run_oracle("loop_consumed", args)
    for potions, scale, row in zip(cases, scales, rows, strict=True):
        live = consumed_seconds(potions)
        if row["none"]:
            assert live is None, potions
        else:
            assert live == Fraction(row["cost"], scale), potions


def test_consumed_witnesses_against_lean() -> None:
    cases: list[list[tuple[int, Fraction | None, int]]] = [
        [(5, Fraction(7), 3)], [(5, Fraction(7), 3), (6, None, 5)], [(2, None, 5)], []]
    rows = run_oracle("loop_consumed", [[len(c)] + [x for u, p, h in c
                                                     for x in (u, 0 if p is None else 1,
                                                               0 if p is None else int(p), h)]
                                        for c in cases])
    assert [None if r["none"] else r["cost"] for r in rows] == [14, None, 0, 0]
    assert [consumed_seconds(c) for c in cases] == [14, None, 0, 0]

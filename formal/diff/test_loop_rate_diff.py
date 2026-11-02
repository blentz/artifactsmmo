"""Differential tests for consumable utility increments 3-4: the live
`ai/loop_rate_core.recovery_choice` / `consumed_seconds` / `xp_per_second` must
agree with the proved `Formal.LoopRate.recovery` / `planCost` / `consumedPrice` /
`xpRate`, and the bank trips (`drops_per_fight` / `trip_seconds` /
`trip_share`, spec 2026-10-18 §2.10) with `dropsPerFight` / `tripSeconds` /
`tripShare`. The chosen count vector must COST the proved minimum (`planCost`
of it equals `recovery`), so the counts the floor reads are an optimal plan.

The Lean model works on ONE common scale: every price and the eat cooldown are
passed multiplied by the lcm of their denominators, and the Lean recovery is
that scale times the Python `Fraction` (a minimum of sums is homogeneous).
Inputs stay small because the Lean recovery is the plain recursion over count
vectors (no memo): ≤ 3 foods, restores ≥ 6 and ≤ 160 HP missing."""

from fractions import Fraction
from math import lcm

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.chosen_loadout import food_shares
from artifactsmmo_cli.ai.loop_rate_core import (
    Food,
    consumed_seconds,
    drops_per_fight,
    expected_xp_per_second,
    recovery_choice,
    recovery_seconds,
    trip_seconds,
    trip_share,
    xp_per_second,
)
from formal.diff.oracle_client import run_oracle

_price = st.fractions(min_value=0, max_value=60, max_denominator=12)
_food = st.tuples(st.integers(min_value=6, max_value=120), st.one_of(st.none(), _price),
                  st.integers(min_value=0, max_value=4),
                  st.integers(min_value=0, max_value=30))          # room (Task 8c)
_recovery_case = st.tuples(
    st.integers(min_value=-3, max_value=160),                   # missing
    st.integers(min_value=1, max_value=400),                    # max hp
    st.lists(_food, max_size=3),
    st.one_of(st.just(Fraction(3)), _price),                    # eat seconds
    st.integers(min_value=0, max_value=40),                     # bag room (fix round 1)
    st.integers(min_value=0, max_value=3),                      # bag slots
)
_Case = tuple[int, int, list[Food], Fraction, int, int]


def _scale(values: list[Fraction]) -> int:
    return lcm(1, *(v.denominator for v in values))


def _recovery_args(missing: int, max_hp: int, food: list[Food], eat: Fraction, qty: int,
                   slots: int) -> tuple[int, list[int]]:
    scale = _scale([eat, *(p for _, p, _, _ in food if p is not None)])
    args = [scale, int(eat * scale), max_hp, max(0, missing), qty, slots, len(food)]
    for restore, price, held, room in food:
        args += [restore, 0 if price is None else 1, 0 if price is None else int(price * scale), held,
                 room]
    return scale, args


def _feasible(food: list[Food], counts: tuple[int, ...], qty: int, slots: int) -> bool:
    """`Formal.LoopRate.feasible` of the chosen counts (review minor 2): each
    food within its room and, with no replacement, its held units; the units
    within the bag's room and the foods eaten within its slots. `planCost`
    ignores both, so the cost check alone cannot see an infeasible vector."""
    return (all(k <= room and (price is not None or k <= held)
                for k, (_, price, held, room) in zip(counts, food, strict=True))
            and sum(counts) <= qty and sum(1 for k in counts if k > 0) <= slots)


@settings(max_examples=200, deadline=None)
@given(cases=st.lists(_recovery_case, min_size=1, max_size=20))
def test_recovery_matches_lean(cases: list[_Case]) -> None:
    built = [_recovery_args(*case) for case in cases]
    rows = run_oracle("loop_recovery", [args for _, args in built])
    choices = [recovery_choice(*case) for case in cases]
    costs = run_oracle("loop_plan_cost", [args + list(counts)
                                          for (_, args), (_, counts) in zip(built, choices, strict=True)])
    for case, (scale, _), row, (value, counts), cost in zip(cases, built, rows, choices, costs,
                                                            strict=True):
        assert value == Fraction(row["recovery"], scale), case
        assert recovery_seconds(*case) == value, case
        assert Fraction(cost["cost"], scale) == value, case
        _, _, food, _, qty, slots = case
        assert _feasible(food, counts, qty, slots), case


def test_recovery_witnesses_against_lean() -> None:
    """The Lean file's witnesses, through the oracle and the live code."""
    cases: list[_Case] = [
        (60, 100, [], Fraction(3), 10, 1),
        (60, 100, [(50, Fraction(0), 0, 2)], Fraction(3), 10, 1),
        (60, 100, [(50, Fraction(40), 0, 2)], Fraction(3), 10, 1),
        (60, 100, [(50, Fraction(60), 0, 2)], Fraction(3), 10, 1),
        (60, 100, [(50, Fraction(60), 2, 2)], Fraction(3), 10, 1),
        (60, 100, [(50, None, 1, 2)], Fraction(3), 10, 1),
        (0, 100, [(50, Fraction(0), 0, 2)], Fraction(3), 10, 1),
        (1, 100, [], Fraction(3), 10, 1),
        (250, 100, [], Fraction(3), 10, 1),
        # Task 8c: room for one unit, then for none (the Rest fallback).
        (60, 100, [(50, Fraction(0), 0, 1)], Fraction(3), 10, 1),
        (60, 100, [(50, Fraction(0), 0, 0)], Fraction(3), 10, 1),
        # Fix round 1, ONE room: scenario A (two stacks, then one), scenario B
        # (five units of room), and a bag with no stack / no units: Rest.
        (80, 100, [(10, None, 3, 100), (30, Fraction(5), 0, 100)], Fraction(3), 100, 2),
        (80, 100, [(10, None, 3, 100), (30, Fraction(5), 0, 100)], Fraction(3), 100, 1),
        (80, 100, [(10, Fraction(1), 0, 100), (10, Fraction(1), 0, 100)], Fraction(3), 5, 2),
        (60, 100, [(50, Fraction(0), 0, 2)], Fraction(3), 10, 0),
        (60, 100, [(50, Fraction(0), 0, 2)], Fraction(3), 0, 1),
    ]
    expected = [60, 3, 53, 60, 3, 13, 0, 3, 100, 13, 60, 16, 18, 38, 60, 60]
    built = [_recovery_args(*case) for case in cases]
    rows = run_oracle("loop_recovery", [args for _, args in built])
    assert [Fraction(row["recovery"], scale) for (scale, _), row in zip(built, rows, strict=True)] == expected
    assert [recovery_seconds(*case) for case in cases] == expected


_share_food = st.tuples(st.integers(min_value=0, max_value=8), st.integers(min_value=0, max_value=6))


@settings(max_examples=300, deadline=None)
@given(cases=st.lists(st.tuples(st.lists(_share_food, max_size=4), st.integers(min_value=0, max_value=4),
                                st.integers(min_value=0, max_value=60)), min_size=1, max_size=20))
def test_shares_match_lean(cases: list[tuple[list[tuple[int, int]], int, int]]) -> None:
    """`chosen_loadout.food_shares` is `Formal.LoopRate.shares` (fix round 1)."""
    rows = run_oracle("loop_shares", [[slots, free, len(foods), *(v for f in foods for v in f)]
                                      for foods, slots, free in cases])
    for (foods, slots, free), row in zip(cases, rows, strict=True):
        assert list(food_shares(foods, slots, free)) == row["shares"], (foods, slots, free)


def test_shares_witnesses_against_lean() -> None:
    cases = [([(3, 0), (5, 0)], 2, 16), ([(3, 0), (5, 0)], 1, 16), ([(3, 4), (5, 0)], 0, 12)]
    rows = run_oracle("loop_shares", [[slots, free, len(foods), *(v for f in foods for v in f)]
                                      for foods, slots, free in cases])
    assert [row["shares"] for row in rows] == [[6, 10], [0, 0], [16, 0]]
    assert [list(food_shares(*case)) for case in cases] == [[6, 10], [0, 0], [16, 0]]


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


_p_win = st.fractions(min_value=0, max_value=1, max_denominator=40)
_expected_case = st.tuples(
    _p_win, st.integers(min_value=0, max_value=5000),
    st.fractions(min_value=Fraction(1, 20), max_value=120, max_denominator=20),
    _seconds,
)


@settings(max_examples=300, deadline=None)
@given(cases=st.lists(_expected_case, min_size=1, max_size=30))
def test_expected_xp_rate_matches_lean(cases: list[tuple[Fraction, int, Fraction, Fraction]]) -> None:
    args = [[p.numerator, p.denominator, xp, fight.numerator, fight.denominator,
             extra.numerator, extra.denominator] for p, xp, fight, extra in cases]
    rows = run_oracle("expected_xp_rate", args)
    for (p, xp, fight, extra), row in zip(cases, rows, strict=True):
        assert expected_xp_per_second(xp, p, fight, extra) == Fraction(row["rate_num"], row["rate_den"]), \
            (p, xp, fight, extra)


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


_unit = st.fractions(min_value=0, max_value=3, max_denominator=300)
_trip_case = st.tuples(
    _p_win, st.lists(_unit, max_size=4),
    st.integers(min_value=0, max_value=400),                    # walk seconds
    st.fractions(min_value=0, max_value=5, max_denominator=4),  # deposit seconds
    st.integers(min_value=0, max_value=6),                      # codes
    st.integers(min_value=-5, max_value=200),                   # capacity
)
_TripCase = tuple[Fraction, list[Fraction], int, Fraction, int, int]


def _trip_args(case: _TripCase) -> list[int]:
    p, units, walk, deposit, codes, capacity = case
    args = [p.numerator, p.denominator, len(units)]
    for unit in units:
        args += [unit.numerator, unit.denominator]
    return [*args, walk, deposit.numerator, deposit.denominator, codes, capacity]


def _check_trips(cases: list[_TripCase]) -> None:
    rows = run_oracle("loop_trips", [_trip_args(case) for case in cases])
    for case, row in zip(cases, rows, strict=True):
        p, units, walk, deposit, codes, capacity = case
        drops = drops_per_fight(p, units)
        trip = trip_seconds(walk, deposit, codes)
        assert drops == Fraction(row["drops_num"], row["drops_den"]), case
        assert trip == Fraction(row["trip_num"], row["trip_den"]), case
        share = trip_share(trip, drops, capacity)
        if row["none"]:
            assert share is None, case
        else:
            assert share == Fraction(row["share_num"], row["share_den"]), case


@settings(max_examples=300, deadline=None)
@given(cases=st.lists(_trip_case, min_size=1, max_size=30))
def test_trips_match_lean(cases: list[_TripCase]) -> None:
    _check_trips(cases)


def test_trip_witnesses_against_lean() -> None:
    """The Lean file's witnesses: a 104 s trip, its share into a bag of 20, no
    room with drops, no room without them, and a loss that drops nothing."""
    _check_trips([
        (Fraction(1), [Fraction(1), Fraction(1)], 50, Fraction(2), 2, 20),
        (Fraction(1), [Fraction(1), Fraction(1)], 50, Fraction(2), 2, 0),
        (Fraction(1), [], 50, Fraction(2), 2, 0),
        (Fraction(0), [Fraction(3)], 50, Fraction(2), 1, -1),
    ])
    assert trip_share(trip_seconds(50, Fraction(2), 2), Fraction(2), 20) == Fraction(104, 10)
    assert trip_share(Fraction(104), Fraction(2), 0) is None
    assert trip_share(Fraction(104), Fraction(0), 0) == 0

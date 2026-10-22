"""Differential test for spec 2026-10-18 §2.8: the live
`ai/drop_chance_core` (`posterior_chance`, `chance_at`, `fit_k`) must agree with
the proved `Formal.DropChance` (`posterior`, `chance`, `fitK`) on random rates,
observations, slopes and prospecting of either sign, including the floor of
the multiplier, the cap at 1, the clamp of `k` and a fit with no positive
prospecting."""

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.drop_chance_core import chance_at, fit_k, posterior_chance, units_per_attempt
from formal.diff.oracle_client import run_oracle


@st.composite
def _observation(draw: st.DrawFn) -> tuple[int, int, int]:
    """`(api_rate, attempts, hits)` with `hits <= attempts`."""
    api_rate = draw(st.integers(min_value=1, max_value=1000))
    attempts = draw(st.integers(min_value=0, max_value=2000))
    hits = draw(st.integers(min_value=0, max_value=attempts))
    return api_rate, attempts, hits


_chance_case = st.tuples(
    _observation(),
    st.fractions(min_value=-2, max_value=2, max_denominator=50),   # k
    st.integers(min_value=-50, max_value=200),                     # prospecting
)


@st.composite
def _sample(draw: st.DrawFn) -> tuple[int, int, int, int]:
    """`(api_rate, prospecting, attempts, hits)` with `hits <= attempts`."""
    api_rate, attempts, hits = draw(_observation())
    return api_rate, draw(st.integers(min_value=-20, max_value=100)), attempts, hits


def _frac(row: dict[str, object], num: str = "num", den: str = "den") -> Fraction:
    return Fraction(int(row[num]), int(row[den]))  # type: ignore[call-overload]


def _chance_args(api_rate: int, attempts: int, hits: int, k: Fraction,
                 prospecting: int) -> list[int]:
    return [api_rate, attempts, hits, k.numerator, k.denominator, prospecting]


def _fit_args(samples: list[tuple[int, int, int, int]]) -> list[int]:
    return [len(samples), *(value for sample in samples for value in sample)]


@settings(max_examples=300, deadline=None)
@given(cases=st.lists(_chance_case, min_size=1, max_size=30))
def test_drop_chance_matches_lean(
        cases: list[tuple[tuple[int, int, int], Fraction, int]]) -> None:
    flat = [(*observation, k, prospecting) for observation, k, prospecting in cases]
    rows = run_oracle("drop_chance", [_chance_args(*case) for case in flat])
    for case, row in zip(flat, rows, strict=True):
        assert chance_at(*case) == _frac(row), case
        assert posterior_chance(*case[:3]) == _frac(row, "postNum", "postDen"), case


@settings(max_examples=300, deadline=None)
@given(cases=st.lists(st.tuples(_chance_case, st.integers(min_value=1, max_value=10),
                                st.integers(min_value=0, max_value=10)),
                      min_size=1, max_size=30))
def test_units_per_attempt_matches_lean(
        cases: list[tuple[tuple[tuple[int, int, int], Fraction, int], int, int]]) -> None:
    """`units_per_attempt` (ruling T16a, the one drop model) against
    `Formal.DropChance.units`: the chance times the mean of `min..min+extra`."""
    flat = [((*observation, k, prospecting), min_q, min_q + extra)
            for (observation, k, prospecting), min_q, extra in cases]
    rows = run_oracle("drop_units", [[*_chance_args(*chance), min_q, max_q]
                                     for chance, min_q, max_q in flat])
    for (chance, min_q, max_q), row in zip(flat, rows, strict=True):
        api_rate, attempts, hits, k, prospecting = chance
        assert units_per_attempt(api_rate, min_q, max_q, attempts, hits, k,
                                 prospecting) == _frac(row), (chance, min_q, max_q)


def test_units_edges_against_lean() -> None:
    """The prior pearl (1/300), the live trout_spot pearls (3/683), a drop of
    1 to 3 at 1 in 8 (1/4), and a capped chance times a mean of 2."""
    cases = [(300, 0, 0, Fraction(0), 0, 1, 1), (300, 383, 2, Fraction(0), 0, 1, 1),
             (8, 0, 0, Fraction(0), 0, 1, 3), (1, 0, 0, Fraction(1, 5), 10, 1, 3)]
    rows = run_oracle("drop_units", [[*_chance_args(*case[:5]), case[5], case[6]]
                                     for case in cases])
    expected = [Fraction(1, 300), Fraction(3, 683), Fraction(1, 4), Fraction(2)]
    assert [_frac(row) for row in rows] == expected
    assert [units_per_attempt(r, mn, mx, a, h, k, p)
            for r, a, h, k, p, mn, mx in cases] == expected


@settings(max_examples=300, deadline=None)
@given(sets=st.lists(st.lists(_sample(), max_size=8), min_size=1, max_size=10))
def test_fit_k_matches_lean(sets: list[list[tuple[int, int, int, int]]]) -> None:
    rows = run_oracle("drop_fit_k", [_fit_args(samples) for samples in sets])
    for samples, row in zip(sets, rows, strict=True):
        assert fit_k(samples) == _frac(row), samples


def test_edges_against_lean() -> None:
    """The prior; the live trout_spot pearls; a multiplier of 3 on the prior;
    the cap at 1; a negative slope floored at 1."""
    cases = [
        (300, 0, 0, Fraction(0), 0),
        (300, 383, 2, Fraction(0), 25),
        (300, 0, 0, Fraction(1, 5), 10),
        (1, 0, 0, Fraction(1, 5), 10),
        (300, 0, 0, Fraction(-1), 5),
    ]
    rows = run_oracle("drop_chance", [_chance_args(*case) for case in cases])
    expected = [Fraction(1, 300), Fraction(3, 683), Fraction(1, 100), Fraction(1),
                Fraction(1, 300)]
    assert [_frac(row) for row in rows] == expected
    assert [chance_at(*case) for case in cases] == expected


def test_fit_edges_against_lean() -> None:
    """The weighted slope 1/10; no samples; a clamped slope; a slope fitted
    only at a negative prospecting; a sample without attempts."""
    sets = [
        [(300, 10, 100, 1), (100, 20, 50, 1), (300, 0, 383, 2)],
        [],
        [(300, 10, 300, 0)],
        [(300, -5, 300, 0)],
        [(300, 10, 100, 1), (300, 40, 0, 0)],
    ]
    rows = run_oracle("drop_fit_k", [_fit_args(samples) for samples in sets])
    expected = [Fraction(1, 10), Fraction(0), Fraction(0), Fraction(0), Fraction(1, 5)]
    assert [_frac(row) for row in rows] == expected
    assert [fit_k(samples) for samples in sets] == expected

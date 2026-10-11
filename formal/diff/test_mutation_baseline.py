"""Unit tests for the mutation gate's baseline check (`mutation_baseline`)."""

from pathlib import Path

from formal.diff.mutation_baseline import drop_red, red_baselines

SRC = Path("src/x.py")
UNITS = [(SRC, "a", "o", "n", "tests/green.py"), (SRC, "b", "o", "n", "tests/red.py"),
         (SRC, "c", "o", "n", "tests/green.py"), (SRC, "d", "o", "n", "tests/red.py")]


def test_each_kill_test_runs_once_and_the_failing_ones_are_red() -> None:
    ran: list[str] = []

    def run(test: str) -> int:
        ran.append(test)
        return 1 if "red" in test else 0

    assert red_baselines(UNITS, run, workers=4) == ["tests/red.py"]
    assert sorted(ran) == ["tests/green.py", "tests/red.py"]


def test_a_harness_error_is_red_too() -> None:
    assert red_baselines(UNITS[:1], lambda _t: 2, workers=1) == ["tests/green.py"]


def test_no_units_no_runs() -> None:
    assert red_baselines([], lambda _t: 1, workers=4) == []


def test_units_of_a_red_test_are_errors_not_kills() -> None:
    errored: list[str] = []
    survivors: list[str] = []
    kept = drop_red(UNITS, ["tests/red.py"], errored, survivors)
    assert [u[1] for u in kept] == ["a", "c"]
    assert errored == ["b (kill-test red unmutated: tests/red.py)",
                       "d (kill-test red unmutated: tests/red.py)"]
    assert survivors == ["b (harness rc=baseline)", "d (harness rc=baseline)"]
    assert drop_red(UNITS, [], errored, survivors) == UNITS

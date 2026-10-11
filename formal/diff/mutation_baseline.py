"""The mutation gate's baseline check: a kill-test must PASS on the unmutated
tree, or none of its "kills" mean anything.

A mutant is counted killed when its kill-test fails. A test that fails anyway
— an unrelated regression, a fixture bug, a missing dependency — fails for
every mutant it is given, so the gate read OK over a broken suite: live
2026-10-11, a `--only` sweep reported "mutation gate OK" while the party-hold
test it ran failed on the clean tree (an unset `game_data`). Every distinct
kill-test now runs once, unmutated, before any mutation; the units whose test
is red are reported as harness errors and never run."""

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

Unit = tuple[Path, str, str, str, str]
"""(target src file, description, old text, new text, kill-test path)."""


def red_baselines(units: Sequence[Unit], run: Callable[[str], int], workers: int) -> list[str]:
    """The kill-tests `run` reports failing (rc != 0) on the unmutated tree,
    each run once, in first-use order; read-only, so run in parallel."""
    tests = list(dict.fromkeys(unit[4] for unit in units))
    if not tests:
        return []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(tests)))) as pool:
        codes = list(pool.map(run, tests))
    return [test for test, rc in zip(tests, codes, strict=True) if rc != 0]


def drop_red(units: Sequence[Unit], red: Sequence[str], errored: list[str],
             survivors: list[str]) -> list[Unit]:
    """`units` without those whose kill-test is red; each dropped unit is
    recorded in `errored` and `survivors` (the gate fails on it)."""
    kept: list[Unit] = []
    for unit in units:
        if unit[4] in red:
            errored.append(f"{unit[1]} (kill-test red unmutated: {unit[4]})")
            survivors.append(unit[1] + " (harness rc=baseline)")
        else:
            kept.append(unit)
    return kept

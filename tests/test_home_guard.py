"""Proves the suite-wide `~/.cache/artifactsmmo` write guard actually works.

See `conftest.py`'s `artifactsmmo_test_home` fixture docstring for the
interception point (`pathlib.Path.home`) and the incident that motivated it
(Task 11, round 3, 2026-08-01: a mutation-testing run destroyed the real
`~/.cache/artifactsmmo/learning.db`, with no backup, because a test's write
landed on the genuine default path instead of `tmp_path`).

These tests perform REAL writes through the REAL default-path resolution
function and REAL store constructors — the exact class of operation that
caused the incident — and assert the result lands under the redirected temp
home, never anywhere the genuine user home resolves to.
"""

import os
import pwd
from datetime import datetime, timezone
from pathlib import Path

from artifactsmmo_cli.ai.learning.coordination_store import CoordinationStore
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.learning_db_path import default_learn_db_path


def _true_home() -> Path:
    """The genuine OS home directory, determined WITHOUT going through
    `pathlib.Path.home()` (which `artifactsmmo_test_home` deliberately
    redirects for the whole suite) or the `HOME` environment variable
    (which the same fixture also redirects) — reads straight from `pwd`,
    the same source `os.path.expanduser` falls back to when `HOME` is
    unset. Independent of the guard under test, on purpose: this is the
    value the guard exists to protect."""
    return Path(pwd.getpwuid(os.getuid()).pw_dir)


def test_path_home_is_redirected_away_from_the_real_home(artifactsmmo_test_home):
    assert Path.home() == artifactsmmo_test_home
    assert Path.home() != _true_home()


def test_home_env_var_is_also_redirected(artifactsmmo_test_home):
    assert os.environ["HOME"] == str(artifactsmmo_test_home)


def test_default_learn_db_path_resolves_under_the_redirected_home(artifactsmmo_test_home):
    resolved = Path(default_learn_db_path())
    assert resolved.is_relative_to(artifactsmmo_test_home)
    assert not resolved.is_relative_to(_true_home())


def test_a_real_learning_store_write_through_the_default_path_stays_sandboxed(
    artifactsmmo_test_home,
):
    """The exact class of operation that caused the 2026-08-01 incident:
    construct a store against the DEFAULT path (no explicit `tmp_path`) and
    perform a real write (`start_session` inserts a `Session` row)."""
    db_path = default_learn_db_path()
    store = LearningStore(db_path=db_path, character="home-guard-test")
    try:
        store.start_session()
    finally:
        store.close()

    written = Path(db_path)
    assert written.exists()
    assert written.is_relative_to(artifactsmmo_test_home)
    real_equivalent = _true_home() / ".cache" / "artifactsmmo" / "learning.db"
    assert written != real_equivalent


def test_a_real_coordination_store_write_through_the_default_path_stays_sandboxed(
    artifactsmmo_test_home,
):
    """Task 11's own consumer of `default_learn_db_path()` — the path
    `MultiRun._coordination_db_path` reuses when `--learn` is on — performing
    the same class of write (`claim` inserts a `RoleLease` row)."""
    db_path = default_learn_db_path()
    store = CoordinationStore(db_path=db_path, character="home-guard-test")
    try:
        store.claim("miner", datetime.now(tz=timezone.utc))
    finally:
        store.close()

    written = Path(db_path)
    assert written.exists()
    assert written.is_relative_to(artifactsmmo_test_home)
    real_equivalent = _true_home() / ".cache" / "artifactsmmo" / "learning.db"
    assert written != real_equivalent

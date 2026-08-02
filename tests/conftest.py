"""Test-suite-wide fixtures.

Colour environment. Rich and Textual both read the ambient colour env, and the
two halves of this suite want OPPOSITE things:

* command tests drive Typer/Rich through CliRunner and assert PLAIN-TEXT
  substrings, so `FORCE_COLOR` makes them fail on embedded ANSI escapes;
* the Textual TUI tests need a colour-capable terminal, so `NO_COLOR` breaks
  them instead.

`scripts/run_tests.sh` unsets both before invoking pytest, which is why the
suite is green through the runner. But a bare `uv run pytest tests/` inherits
whatever the developer's shell exports -- and in a terminal that sets
`FORCE_COLOR` that means ~12 spurious failures in test_commands/, test_bank,
test_character, test_pathfinding_commands and test_integration, all of them
assertions on strings that now contain `\\x1b[` escapes. That looks exactly like
a real regression, which is how it cost time.

Clearing both here makes the suite env-independent, so the runner and a direct
pytest invocation agree.
"""

import os
import tempfile
from pathlib import Path

import pytest

# Cleared at conftest IMPORT time, not from a fixture. pytest imports conftest
# before it collects test modules, and Rich reads the colour env when a Console
# is constructed -- which happens at module import for anything holding a
# module-level Console. A session-scoped autouse fixture runs too late: the
# Console already exists with colour forced on. Deleted rather than set to ""
# because Rich treats an empty-but-present FORCE_COLOR as still set.
for _colour_var in ("FORCE_COLOR", "NO_COLOR"):
    os.environ.pop(_colour_var, None)


@pytest.fixture(autouse=True, scope="session")
def artifactsmmo_test_home():
    """Suite-wide guard: no test may ever write to the REAL
    `~/.cache/artifactsmmo/*` (learning DB, coordination DB, static
    game-data cache) — whatever the code under test does.

    This exists because of a real incident (Task 11, round 2, 2026-08-01): a
    mutation-testing run briefly inverted one conditional in
    `MultiRun._coordination_db_path`, and a test's simulated write — which
    was correctly scoped to `tmp_path` under the INTENDED code path — landed
    on the genuine `~/.cache/artifactsmmo/learning.db` instead, because the
    mutated conditional silently redirected `default_learn_db_path()` to the
    real path. That destroyed the account's actual learned-stats history
    (sessions, cycles, learned_settings) with no backup. The fix belongs at
    suite level, not in whichever test happens to touch a default path next.

    INTERCEPTION POINT: `pathlib.Path.home`, not `default_learn_db_path()`
    (`learning_db_path.py`) and not individual store constructors. Grepping
    `Path.home()` across `src/` turns up SIX call sites funnelling into
    `~/.cache/artifactsmmo`: `learning_db_path.default_learn_db_path` (the
    one Task 11 actually uses), `ai/game_data_cache.py`'s static game-data
    cache, and FOUR separate hand-rolled duplicates of the exact same
    `Path.home() / ".cache" / "artifactsmmo" / "learning.db"` expression in
    `commands/plan.py`, `commands/stats.py`, `commands/macro_research.py`,
    and `commands/combat_loadout_report.py`. Patching `default_learn_db_path`
    alone — the fix that would have been "easy" — would leave those other
    five exposed to the identical hazard the moment a future test constructs
    a real store against one of them, no mutation testing required: a plain
    string-comparison test turning into a real constructor call is enough,
    which is exactly how the original incident happened (`_coordination_db_path`
    is not `default_learn_db_path` — it CALLS it, one indirection the
    "patch the function" approach would also have had to chase). `Path.home()`
    is the one primitive every current call site shares, and the one a
    future duplicate would almost certainly share too (it is what `Path`
    itself offers for "the user's home directory" — nobody hand-rolls
    `os.environ["HOME"]` when `Path.home()` exists).

    BELT AND BRACES: the `HOME` environment variable is also redirected.
    `Path.home()` resolves via `os.path.expanduser("~")` on POSIX, which
    reads `HOME` first, so this is redundant with the direct patch for
    every call site above — but it independently covers any future code
    that reads `os.path.expanduser` or `$HOME` directly instead of going
    through `pathlib.Path.home()`.

    Session-scoped: one temp directory, patched once, for the whole run.
    Nothing here is per-test state, so function scope would only add a
    fresh temp directory (and teardown) to every single test for no
    benefit — `pytest.MonkeyPatch()` (not the function-scoped `monkeypatch`
    fixture, which cannot be requested at session scope) is used directly
    so the patch can be undone deterministically at session end regardless.
    """
    with tempfile.TemporaryDirectory(prefix="artifactsmmo-test-home-") as fake_home:
        mp = pytest.MonkeyPatch()
        mp.setattr(Path, "home", staticmethod(lambda: Path(fake_home)))
        mp.setenv("HOME", fake_home)
        try:
            yield Path(fake_home)
        finally:
            mp.undo()

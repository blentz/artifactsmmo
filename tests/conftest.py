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

# Cleared at conftest IMPORT time, not from a fixture. pytest imports conftest
# before it collects test modules, and Rich reads the colour env when a Console
# is constructed -- which happens at module import for anything holding a
# module-level Console. A session-scoped autouse fixture runs too late: the
# Console already exists with colour forced on. Deleted rather than set to ""
# because Rich treats an empty-but-present FORCE_COLOR as still set.
for _colour_var in ("FORCE_COLOR", "NO_COLOR"):
    os.environ.pop(_colour_var, None)

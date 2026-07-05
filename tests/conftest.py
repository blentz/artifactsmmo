"""Repo-wide test environment normalization.

Runs before test modules import the CLI package, whose module-level rich
Consoles capture the color environment at construction. A colored host
environment (FORCE_COLOR / COLORTERM from CI or IDE shells) makes rich
emit ANSI escapes into CliRunner captures, breaking every plain-substring
assertion on command output. Tests must not depend on the invoking shell.
"""

import os

# Only the FORCE overrides are removed: without them rich falls back to
# isatty detection and CliRunner captures stay plain. NO_COLOR is NOT set
# — textual honors it and would strip the styles the TUI tests assert on.
os.environ.pop("FORCE_COLOR", None)
os.environ.pop("COLORTERM", None)

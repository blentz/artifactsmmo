"""Fresh-interpreter import-order regression test (2026-08-01 fix).

`role_catalog` used to be importable ONLY because some other module happened
to be imported first, establishing an order where `artifactsmmo_cli.ai.tiers`
(triggered by `role_catalog`'s own `from ...tiers.skill_classes import ...`)
completed its `progression_tree -> role_catalog` chain before `role_catalog`
itself resumed past that line. `import artifactsmmo_cli.ai.role_catalog` as
the FIRST project import raised:

    ImportError: cannot import name 'ROLE_CATALOG' from partially
    initialized module 'artifactsmmo_cli.ai.role_catalog' (most likely due
    to a circular import)

The fix: `ai.tiers.progression_tree._role_map` no longer imports
`role_catalog` at all — it takes the role's owned skills (a `frozenset[str]`)
straight from `SelectionContext.role_skills`, resolved once by
`GamePlayer._role_owned_skills` on the `player.py` side of the boundary,
which already depends on `role_catalog` for `decide_role`/`demand_by_role`
and is never itself imported by the `ai.tiers` package.

Each case below launches `sys.executable -c "import X"` in a SUBPROCESS — a
brand-new interpreter with an empty `sys.modules` — because importing inside
the current test process proves nothing: by the time any test runs, pytest
collection has already imported most of the package graph, so every entry
point below would resolve regardless of whether the cycle is actually fixed.
"""

import subprocess
import sys

import pytest

# Every module confirmed BROKEN or AT-RISK as the first project import before
# the fix: `role_catalog` (the module the bug report traced) and
# `role_selection` (imports `role_catalog` at module scope, so it hits the
# identical partially-initialized-module error) were both broken; the rest
# happened to load safely with the pre-fix code (their own import order never
# routed back into `role_catalog` mid-init) but are included as plausible
# entry points a future refactor could just as easily re-break.
ENTRY_POINTS = [
    "artifactsmmo_cli.ai.role_catalog",
    "artifactsmmo_cli.ai.role_selection",
    "artifactsmmo_cli.ai.role_alignment",
    "artifactsmmo_cli.ai.tiers.progression_tree",
    "artifactsmmo_cli.ai.player",
    "artifactsmmo_cli.ai.selection_context",
]


@pytest.mark.parametrize("module", ENTRY_POINTS)
def test_module_imports_cleanly_as_the_first_project_import(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr


def test_role_catalog_first_import_does_not_raise_the_traced_circular_import() -> None:
    """Reproduces the exact bug-report repro line verbatim, asserting the
    specific `ImportError` message is gone (not just that SOME error is
    gone)."""
    result = subprocess.run(
        [sys.executable, "-c", "import artifactsmmo_cli.ai.role_catalog"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0
    assert "circular import" not in result.stderr
    assert "ROLE_CATALOG" not in result.stderr

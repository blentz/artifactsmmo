"""Ensure the worktree root is importable so `formal` resolves as a package, and
pin a deterministic Hypothesis profile for the differential tests.

The mutation runner rewrites the Python source in place and re-runs the diff tests
against the mutated code. With Hypothesis's default example database, a falsifying
example found on a MUTATED run gets persisted and then replayed on a later CLEAN
run, causing a spurious gate failure. The differential tests are deterministic
equality checks (Lean oracle vs real Python), not regression-seeking, so we disable
the example database and derandomize input generation: this makes the gate
reproducible and immune to cross-run poisoning.
"""
import sys
from pathlib import Path

from hypothesis import settings

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# `deadline=None` disables Hypothesis's per-example 200ms timeout. Each diff test
# invokes the Lean `oracle` subprocess for the comparison, which under heavy gate
# load (mutate.py runs the full diff suite per mutation) can push some examples
# past 200ms — a perf-flake, not a correctness signal. The differential properties
# are deterministic; we don't need the deadline as a regression-finder here.
settings.register_profile("formal", database=None, derandomize=True, deadline=None)
settings.load_profile("formal")

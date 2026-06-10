"""Reader side of the mutate-run <-> play interlock.

``formal/diff/mutate.py`` live-writes mutants into ``src/`` while it runs and
restores them afterwards. Any consumer that imports the package mid-run gets
poisoned code (2026-06-09 incident: ``artifactsmmo play`` launched during a
mutation run imported a mutated predicate and crashed with SystemExit(2)).
The runner drops a lockfile at the repo root for the duration of the run;
this module is the consumer-side probe of that lockfile.

The writer side is implemented inline in ``formal/diff/mutate.py`` (formal/
is not part of the src package, so it cannot import this module) — keep
``MUTATION_LOCKFILE_NAME`` textually identical in both places.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# Keep identical to MUTATION_LOCKFILE in formal/diff/mutate.py.
MUTATION_LOCKFILE_NAME = ".mutation-run.lock"


@dataclass(frozen=True)
class MutationLockStatus:
    """Result of probing the mutation-run lockfile.

    ``state`` is ``absent`` (no lockfile), ``active`` (lockfile names a live
    pid — a mutation run is in progress), or ``stale`` (lockfile left behind
    by a dead or unidentifiable run). ``detail`` says why a lock was judged
    stale.
    """

    state: Literal["absent", "active", "stale"]
    pid: int | None = None
    detail: str = ""


def default_lock_path() -> Path:
    """Lockfile path at the repo root — the same tree whose src/ the mutation
    runner rewrites and this package is imported from."""
    return Path(__file__).resolve().parents[3] / MUTATION_LOCKFILE_NAME


def pid_alive(pid: int) -> bool:
    """True iff ``pid`` is a live process (signal-0 probe).

    ``ProcessLookupError`` means no such process (dead); ``PermissionError``
    means the process exists but belongs to someone else (alive).
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def check_mutation_lock(lock_path: Path) -> MutationLockStatus:
    """Classify the mutation-run lockfile at ``lock_path``.

    The lockfile's first whitespace-separated token is the writer's pid (the
    rest is an informational ISO timestamp). Malformed content — empty file,
    non-integer or non-positive pid — is treated as stale: the file cannot
    prove a live run, and the detail string says what was wrong with it.
    """
    try:
        content = lock_path.read_text()
    except FileNotFoundError:
        return MutationLockStatus(state="absent")
    tokens = content.split()
    if not tokens:
        return MutationLockStatus(state="stale", detail="lockfile is empty")
    try:
        pid = int(tokens[0])
    except ValueError:
        return MutationLockStatus(state="stale", detail=f"malformed pid {tokens[0]!r}")
    if pid <= 0:
        return MutationLockStatus(state="stale", pid=pid, detail=f"non-positive pid {pid}")
    if pid_alive(pid):
        return MutationLockStatus(state="active", pid=pid)
    return MutationLockStatus(state="stale", pid=pid, detail=f"pid {pid} is not running")

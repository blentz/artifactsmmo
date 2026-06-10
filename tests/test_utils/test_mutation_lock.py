"""Tests for the mutate-run lockfile checker (mutate<->play interlock)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from artifactsmmo_cli.utils.mutation_lock import (
    MUTATION_LOCKFILE_NAME,
    check_mutation_lock,
    default_lock_path,
    pid_alive,
)


def _dead_pid() -> int:
    """Spawn a trivial child and reap it: its pid is guaranteed dead."""
    proc = subprocess.Popen([sys.executable, "-c", ""])
    proc.wait()
    return proc.pid


@pytest.fixture
def lock_path(tmp_path: Path) -> Path:
    return tmp_path / MUTATION_LOCKFILE_NAME


class TestPidAlive:
    """Signal-0 liveness probe."""

    def test_own_pid_is_alive(self):
        assert pid_alive(os.getpid()) is True

    def test_reaped_child_pid_is_dead(self):
        assert pid_alive(_dead_pid()) is False

    def test_unsignalable_foreign_pid_counts_as_alive(self):
        # pid 1 (init) exists but is not ours: the probe raises
        # PermissionError, which means the process is alive.
        assert pid_alive(1) is True


class TestCheckMutationLock:
    """Lockfile classification: absent / active / stale."""

    def test_absent_lockfile_is_absent(self, lock_path):
        status = check_mutation_lock(lock_path)
        assert status.state == "absent"
        assert status.pid is None

    def test_live_pid_is_active(self, lock_path):
        lock_path.write_text(f"{os.getpid()}\n2026-06-10T00:00:00+00:00\n")
        status = check_mutation_lock(lock_path)
        assert status.state == "active"
        assert status.pid == os.getpid()

    def test_dead_pid_is_stale(self, lock_path):
        pid = _dead_pid()
        lock_path.write_text(f"{pid}\n2026-06-10T00:00:00+00:00\n")
        status = check_mutation_lock(lock_path)
        assert status.state == "stale"
        assert status.pid == pid
        assert f"pid {pid} is not running" in status.detail

    def test_empty_lockfile_is_stale(self, lock_path):
        lock_path.write_text("")
        status = check_mutation_lock(lock_path)
        assert status.state == "stale"
        assert "empty" in status.detail

    def test_non_integer_pid_is_stale(self, lock_path):
        lock_path.write_text("not-a-pid\n2026-06-10T00:00:00+00:00\n")
        status = check_mutation_lock(lock_path)
        assert status.state == "stale"
        assert "malformed pid 'not-a-pid'" in status.detail

    def test_non_positive_pid_is_stale(self, lock_path):
        # pid 0 would make the signal-0 probe target our own process group
        # and read as "alive"; it must be rejected as unprovable instead.
        lock_path.write_text("0\n2026-06-10T00:00:00+00:00\n")
        status = check_mutation_lock(lock_path)
        assert status.state == "stale"
        assert "non-positive pid 0" in status.detail


class TestDefaultLockPath:
    """The lockfile lives at the repo root, named like mutate.py's constant."""

    def test_points_at_repo_root_lockfile(self):
        path = default_lock_path()
        assert path.name == MUTATION_LOCKFILE_NAME
        # The repo root is the directory that holds pyproject.toml and src/.
        assert (path.parent / "pyproject.toml").is_file()
        assert (path.parent / "src" / "artifactsmmo_cli").is_dir()

    def test_name_matches_mutate_py_writer_side(self):
        # The writer side cannot import this module (formal/ is outside the
        # src package), so the path constant is duplicated by contract.
        mutate_py = default_lock_path().parent / "formal" / "diff" / "mutate.py"
        assert f'ROOT / "{MUTATION_LOCKFILE_NAME}"' in mutate_py.read_text()

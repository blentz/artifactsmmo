"""`play` command: cross-character coordination store attachment (Task 11).

Gated on TWO conditions, not just `--emit-events`:

1. `emit_events` — the flag `MultiRun._child_argv` ALWAYS passes to every
   supervised `play --all` child, and a lone `play <character>` never passes.
   This is the multi-vs-single-character signal.
2. A real, PERSISTED `--learn` db path — coordination is cross-PROCESS by
   construction (siblings are separate subprocesses), so it needs a file on
   disk. `--all` without `--learn` leaves the LearningStore on `:memory:`,
   which SQLite keeps private to this connection; a CoordinationStore opened
   against that same string would get its OWN separate anonymous in-memory
   database, never shared with any sibling.

Mirrors the mocking pattern in `test_play_emit_events.py`: drive the real
`play()` body via `CliRunner`, mocking only `GamePlayer`/`LearningStore`/
`CoordinationStore`.
"""

from unittest.mock import Mock, patch

import typer
from typer.testing import CliRunner

from artifactsmmo_cli.commands import play as play_module

app = typer.Typer()
app.command()(play_module.play)


def _invoke(args):
    runner = CliRunner()
    with (
        patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls,
        patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
        patch("artifactsmmo_cli.commands.play.CoordinationStore") as mock_coord_cls,
    ):
        mock_player = Mock()
        mock_player_cls.return_value = mock_player
        mock_store_cls.return_value = Mock()
        mock_coord = Mock()
        mock_coord_cls.return_value = mock_coord
        result = runner.invoke(app, args)
    return result, mock_player, mock_coord_cls, mock_coord


def test_lone_run_never_attaches_coordination_even_with_a_persisted_learn_db(tmp_path):
    """A single-character run must stay bit-identical: no `--emit-events`
    means no coordination, regardless of `--learn`."""
    db = str(tmp_path / "learn.db")
    result, mock_player, mock_coord_cls, _ = _invoke(["hero", "--learn", "--learn-db", db])
    assert result.exit_code == 0
    mock_coord_cls.assert_not_called()
    mock_player.set_coordination_store.assert_not_called()


def test_emit_events_without_learn_does_not_attach_coordination():
    """An `--all` child without `--learn` runs its LearningStore on
    `:memory:` — private to this process. Attaching a CoordinationStore
    there would be pure per-cycle SQLite overhead for a board no sibling
    could ever see, so it must be skipped."""
    result, mock_player, mock_coord_cls, _ = _invoke(["hero", "--emit-events"])
    assert result.exit_code == 0
    mock_coord_cls.assert_not_called()
    mock_player.set_coordination_store.assert_not_called()


def test_emit_events_with_learn_attaches_coordination_on_the_same_db_path(tmp_path):
    db = str(tmp_path / "learn.db")
    result, mock_player, mock_coord_cls, mock_coord = _invoke(
        ["hero", "--emit-events", "--learn", "--learn-db", db])
    assert result.exit_code == 0
    mock_coord_cls.assert_called_once_with(db_path=db, character="hero")
    mock_player.set_coordination_store.assert_called_once_with(mock_coord)


def test_emit_events_with_default_learn_db_attaches_coordination():
    """`--learn` without `--learn-db` still resolves to a real persisted
    file (`default_learn_db_path()`), so coordination attaches on that."""
    result, mock_player, mock_coord_cls, mock_coord = _invoke(["hero", "--emit-events", "--learn"])
    assert result.exit_code == 0
    mock_coord_cls.assert_called_once_with(
        db_path=play_module.default_learn_db_path(), character="hero")
    mock_player.set_coordination_store.assert_called_once_with(mock_coord)


def test_coordination_store_is_closed_on_normal_exit(tmp_path):
    db = str(tmp_path / "learn.db")
    result, _mock_player, _mock_coord_cls, mock_coord = _invoke(
        ["hero", "--emit-events", "--learn", "--learn-db", db])
    assert result.exit_code == 0
    mock_coord.close.assert_called_once_with()


def test_coordination_store_is_closed_even_on_a_crash(tmp_path):
    db = str(tmp_path / "learn.db")
    runner = CliRunner()
    with (
        patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls,
        patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
        patch("artifactsmmo_cli.commands.play.CoordinationStore") as mock_coord_cls,
    ):
        mock_player = Mock()
        mock_player.run.side_effect = RuntimeError("boom")
        mock_player_cls.return_value = mock_player
        mock_store_cls.return_value = Mock()
        mock_coord = Mock()
        mock_coord_cls.return_value = mock_coord
        result = runner.invoke(app, ["hero", "--emit-events", "--learn", "--learn-db", db])
    assert result.exit_code != 0
    mock_coord.close.assert_called_once_with()

"""`play` command: cross-character coordination store attachment (Task 11).

Gated purely on `--coordination-db` being set. The ONLY caller that ever
passes it is `MultiRun._child_argv` (always, unconditionally, regardless of
`--learn` — see `tests/test_multi/test_multi_run.py`'s coordination tests
for how `MultiRun` picks that path). A lone `play <character>` never passes
this flag, which is what keeps the single-character path bit-identical.

Round 3 of review replaced the original `emit_events and persisted_db_path is
not None` gate (round 1) with this simpler one: `--learn` no longer has
anything to do with coordination — it means only "persist learned stats" —
because `play --all` WITHOUT `--learn` used to leave coordination silently
inert (a `:memory:` LearningStore has no shared file for a sibling to see).
`MultiRun` now supplies a real, shared, on-disk path either way.

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


def test_lone_run_never_attaches_coordination_even_with_learn(tmp_path):
    """A single-character run must stay bit-identical: no `--coordination-db`
    means no coordination, regardless of `--learn`. A human never passes
    `--coordination-db` by hand — only `MultiRun` does."""
    db = str(tmp_path / "learn.db")
    result, mock_player, mock_coord_cls, _ = _invoke(["hero", "--learn", "--learn-db", db])
    assert result.exit_code == 0
    mock_coord_cls.assert_not_called()
    mock_player.set_coordination_store.assert_not_called()


def test_lone_run_never_attaches_coordination_with_emit_events_alone():
    """`--emit-events` alone (no `--coordination-db`) — the round-1 gate —
    must no longer attach coordination either; only the dedicated flag does."""
    result, mock_player, mock_coord_cls, _ = _invoke(["hero", "--emit-events"])
    assert result.exit_code == 0
    mock_coord_cls.assert_not_called()
    mock_player.set_coordination_store.assert_not_called()


def test_coordination_db_attaches_a_coordination_store(tmp_path):
    db = str(tmp_path / "coord.db")
    result, mock_player, mock_coord_cls, mock_coord = _invoke(
        ["hero", "--emit-events", "--coordination-db", db])
    assert result.exit_code == 0
    mock_coord_cls.assert_called_once_with(db_path=db, character="hero")
    mock_player.set_coordination_store.assert_called_once_with(mock_coord)


def test_coordination_db_attaches_independently_of_learn(tmp_path):
    """The whole point of round 3: coordination must not depend on
    `--learn`. Here `--learn` is OFF (so the LearningStore is `:memory:`)
    but `--coordination-db` still attaches a real CoordinationStore on its
    own path."""
    db = str(tmp_path / "coord.db")
    result, mock_player, mock_coord_cls, mock_coord = _invoke(
        ["hero", "--emit-events", "--coordination-db", db])
    assert result.exit_code == 0
    mock_coord_cls.assert_called_once_with(db_path=db, character="hero")
    mock_player.set_coordination_store.assert_called_once_with(mock_coord)


def test_coordination_db_and_learn_together_use_their_own_paths(tmp_path):
    """`--learn-db` and `--coordination-db` are independent knobs (even
    though `MultiRun` happens to pass the SAME value for both when `--learn`
    is on) — `play` must not conflate them."""
    learn_db = str(tmp_path / "learn.db")
    coord_db = str(tmp_path / "coord.db")
    with (
        patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls,
        patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
        patch("artifactsmmo_cli.commands.play.CoordinationStore") as mock_coord_cls,
    ):
        mock_player_cls.return_value = Mock()
        mock_store_cls.return_value = Mock()
        mock_coord_cls.return_value = Mock()
        runner = CliRunner()
        result = runner.invoke(app, [
            "hero", "--learn", "--learn-db", learn_db,
            "--coordination-db", coord_db,
        ])
    assert result.exit_code == 0
    mock_store_cls.assert_called_once_with(db_path=learn_db, character="hero")
    mock_coord_cls.assert_called_once_with(db_path=coord_db, character="hero")


def test_coordination_store_is_closed_on_normal_exit(tmp_path):
    db = str(tmp_path / "coord.db")
    result, _mock_player, _mock_coord_cls, mock_coord = _invoke(
        ["hero", "--emit-events", "--coordination-db", db])
    assert result.exit_code == 0
    mock_coord.close.assert_called_once_with()


def test_coordination_store_is_closed_even_on_a_crash(tmp_path):
    db = str(tmp_path / "coord.db")
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
        result = runner.invoke(app, ["hero", "--emit-events", "--coordination-db", db])
    assert result.exit_code != 0
    mock_coord.close.assert_called_once_with()

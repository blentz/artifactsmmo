"""End-to-end smoke for --learn flag plumbing."""

import subprocess


def test_default_learn_db_path_format():
    from artifactsmmo_cli.commands.play import default_learn_db_path
    path = default_learn_db_path()
    assert path.endswith("learning.db")
    assert "artifactsmmo" in path


def test_play_help_shows_learn_flags():
    result = subprocess.run(
        ["uv", "run", "artifactsmmo", "play", "play", "--help"],
        capture_output=True, text=True, timeout=30,
    )
    assert "--learn" in result.stdout
    assert "--learn-db" in result.stdout

"""Tests for the read-only `objective-audit` CLI command.

The oracle for T1: it combines the root-group, currency-rate and gated-source
censuses (Tasks 3-5) into one report. The live-sense seam (`_sense`, which
would otherwise call the real game API through `GamePlayer.plan_once`) is
substituted with canned state so this test never makes a network call, and the
history store reads a `tmp_path` database seeded through the real
`LearningStore` — the same seam `test_root_group_census.py` uses — rather than
a hand-rolled DB layout that could drift from what production writes.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.commands import objective_audit_report as cmd
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Point the command's history store at an isolated tmp_path database
    instead of the fleet's real `~/.cache/artifactsmmo/learning.db`."""
    path = str(tmp_path / "learning.db")
    monkeypatch.setattr(cmd, "default_learn_db_path", lambda: path)
    return path


@pytest.fixture
def canned_sense(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the live-sense seam with a fixed state and an empty catalogue —
    no real API call, and `gated_xp_sources` legitimately reports nothing
    against a game_data with no monsters."""
    state = make_state(level=5)
    game_data = GameData()
    monkeypatch.setattr(cmd, "_sense", lambda character: (state, game_data))


def _seed_attributed(db: str, character: str) -> None:
    """One measured cycle under a post-migration `root_group`, so `share()`
    is defined and the currency-rate/pareto sections have a row to print."""
    store = LearningStore(db, character=character)
    store.start_session()
    store.record_cycle(Cycle(
        ts="2026-09-21T00:00:00+00:00", session_id="placeholder", cycle_index=0,
        character=character, outcome="ok", selected_goal="GrindCharacterXP(green_slime)",
        root_group="trunk", actual_cooldown_seconds=10.0, delta_xp=30,
        delta_skill_xp_json="{}", delta_gold=5,
    ))
    store.end_session(exit_reason="normal")
    store.close()


def _seed_pre_migration(db: str, character: str) -> None:
    """A cycle written before the `root_group` column existed: `root_group`
    is NULL, so it is `unattributed`, and `attributed == 0` for this character."""
    store = LearningStore(db, character=character)
    store.start_session()
    store.record_cycle(Cycle(
        ts="2026-09-21T00:00:00+00:00", session_id="placeholder", cycle_index=0,
        character=character, outcome="ok", selected_goal="GrindCharacterXP(green_slime)",
        root_group=None, actual_cooldown_seconds=10.0, delta_xp=30,
        delta_skill_xp_json="{}", delta_gold=5,
    ))
    store.end_session(exit_reason="normal")
    store.close()


def test_all_four_section_headers_print(
    db_path: str, canned_sense: None, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_attributed(db_path, "C3P0")

    cmd.objective_audit_command(character="C3P0", window=100)

    out = capsys.readouterr().out
    assert "== root groups (" in out
    assert "== currency rates ==" in out
    assert "== pareto frontier ==" in out
    assert "== gated xp sources (nearest gate first) ==" in out


def test_attributed_row_reports_a_share(
    db_path: str, canned_sense: None, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_attributed(db_path, "C3P0")

    cmd.objective_audit_command(character="C3P0", window=100)

    out = capsys.readouterr().out
    assert "trunk=1 (100.0%)" in out
    assert "GrindCharacterXP(green_slime)" in out


def test_all_pre_migration_takes_the_zero_attributed_branch(
    db_path: str, canned_sense: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """A character whose rows are all pre-migration (`root_group is None`)
    must print the `0 attributed` branch, not raise on `share()` returning
    `None` and not silently skip the character."""
    _seed_pre_migration(db_path, "Robby")

    cmd.objective_audit_command(character="Robby", window=100)

    out = capsys.readouterr().out
    assert "Robby: 0 attributed, 1 pre-migration" in out


def _sensing_player(state: object, game_data: object) -> MagicMock:
    player = MagicMock()
    player.state = state
    player.game_data = game_data
    return player


def test_sense_returns_the_players_state_and_game_data() -> None:
    """`_sense` mirrors `combat_deficit_report.py`'s construction sequence:
    Config -> ClientManager -> an in-memory LearningStore -> GamePlayer.plan_once().
    Config/ClientManager/GamePlayer are substituted so this never touches the
    real token file, API client or network."""
    state = make_state(level=5)
    game_data = GameData()
    player = _sensing_player(state, game_data)
    with (
        patch.object(cmd.Config, "from_token_file",
                     return_value=MagicMock(game_data_ttl_minutes=5)),
        patch.object(cmd, "ClientManager"),
        patch.object(cmd, "GamePlayer", return_value=player),
    ):
        result_state, result_game_data = cmd._sense("C3P0")

    assert result_state is state
    assert result_game_data is game_data
    player.plan_once.assert_called_once()


def test_sense_raises_bad_parameter_when_state_could_not_be_sensed() -> None:
    """An unsensed state must fail loudly, not report an empty audit —
    CLAUDE.md: use only API data or fail with an error."""
    player = _sensing_player(None, GameData())
    with (
        patch.object(cmd.Config, "from_token_file",
                     return_value=MagicMock(game_data_ttl_minutes=5)),
        patch.object(cmd, "ClientManager"),
        patch.object(cmd, "GamePlayer", return_value=player),
    ):
        with pytest.raises(typer.BadParameter, match="could not sense state"):
            cmd._sense("C3P0")


@pytest.fixture
def gated_world() -> tuple[object, object]:
    """One monster (`wolf`) this character cannot beat, whose closing chain
    step (`iron_sword`) is genuinely gated above the held weaponcrafting
    level — the minimal world that exercises `gated_xp_sources`' non-empty
    branch and the command's print line for it. Calibrated the same way as
    `test_xp_gate_census.py`'s `gate_state`/`gate_game_data`: `wolf` fully
    resists fire (so `copper_axe` cannot help) and is hit only by `air`
    (which nothing here resists), so `iron_sword` alone closes it."""
    game_data = GameData()
    game_data._item_stats = {
        "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon",
                                  attack={"air": 2}),
        "iron_sword": ItemStats(code="iron_sword", level=1, type_="weapon",
                                attack={"water": 40},
                                crafting_skill="weaponcrafting", crafting_level=20),
    }
    game_data._monster_level = {"wolf": 3}
    game_data._monster_hp = {"wolf": 200}
    game_data._monster_attack = {"wolf": {"air": 12}}
    game_data._monster_resistance = {"wolf": {"fire": 100, "water": 0}}
    fill_monster_stat_defaults(game_data)
    state = make_state(level=5, hp=150, max_hp=150, equipment={},
                       inventory={"wooden_stick": 1},
                       skills={"weaponcrafting": 1})
    return state, game_data


def test_gated_xp_source_row_prints(
    db_path: str, gated_world: tuple[object, object],
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    _seed_attributed(db_path, "C3P0")
    monkeypatch.setattr(cmd, "_sense", lambda character: gated_world)

    cmd.objective_audit_command(character="C3P0", window=100)

    out = capsys.readouterr().out
    assert "wolf" in out
    assert "blocked by iron_sword (weapon)" in out
    assert "weaponcrafting 1->20" in out

"""Tests for the read-only `sibling-route-audit` CLI command.

The T2 report: it enumerates every craftable item this character is behind
the crafting gate on AND some live sibling clears (ELIGIBLE), asks Task 1's
census (`sibling_route_verdicts`) whether the route was actually priced and
whether it ever changed the price (LOAD-BEARING), and prints all three counts
— even when the lower two are zero, since "eligible 30, priced 0" is the
finding that a gate suppresses the route.

The live-sense seam (`_sense`, which would otherwise call the real game API
through `GamePlayer.plan_once`) is substituted with a self-contained world, and
the coordination/learning stores are pointed at a `tmp_path` database instead
of the fleet's real `~/.cache/artifactsmmo/learning.db` — same two seams
`test_objective_audit_report.py` substitutes, so no real API call and no real
fleet DB write is reachable from this module.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemCatalog, ItemStats
from artifactsmmo_cli.ai.learning.coordination_store import CoordinationStore
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.recipe_catalog import RecipeCatalog
from artifactsmmo_cli.commands import sibling_route_report as cmd
from tests.test_ai.fixtures import coordination_now, make_state

_ALL_SKILLS = {"mining": 3, "woodcutting": 2, "fishing": 1, "weaponcrafting": 1,
               "gearcrafting": 1, "jewelrycrafting": 1, "cooking": 1, "alchemy": 1}


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Point both the coordination and learning stores at an isolated
    `tmp_path` database instead of the fleet's real learning.db — the same
    seam `test_objective_audit_report.py`'s `db_path` fixture substitutes, and
    the same file production reuses for both stores when `--learn` is on
    (`commands/play.py`)."""
    path = str(tmp_path / "learning.db")
    monkeypatch.setattr(cmd, "default_learn_db_path", lambda: path)
    return path


@pytest.fixture
def audit_world() -> tuple[object, object]:
    """A DECLARED, SELF-CONTAINED world (own fixture, not a shared scenario —
    `feedback_scenario_declares_its_world`): two skill-gated items.

    `hexstaff` (weaponcrafting 10) has NO route this character can serve on
    its own — no vendor, no drop, no workshop for weaponcrafting is known — so
    its recipe material `hex_wood` is fully held and its only possible route is
    the sibling craft, exactly as `test_sibling_route_census.py`'s
    `census_world` sets it up. Held weaponcrafting is 1, well below the gate.

    `already_met` (jewelrycrafting 1) is held at jewelrycrafting 3 — already
    AT the gate — so it is INELIGIBLE and must not appear in the eligible
    count even though it names a crafting skill and a sibling holds a level
    for it too."""
    game_data = GameData(
        items=ItemCatalog(stats={
            "hexstaff": ItemStats(code="hexstaff", level=10, type_="weapon",
                                  crafting_skill="weaponcrafting", crafting_level=10),
            "hex_wood": ItemStats(code="hex_wood", level=1, type_="resource"),
            "already_met": ItemStats(code="already_met", level=1, type_="ring",
                                     crafting_skill="jewelrycrafting", crafting_level=1),
        }),
        recipes_catalog=RecipeCatalog(
            crafting_recipes={"hexstaff": {"hex_wood": 4}, "already_met": {"hex_wood": 1}},
            craft_yields={"hexstaff": 1, "already_met": 1},
        ),
    )
    state = make_state(
        skills={**_ALL_SKILLS, "weaponcrafting": 1, "jewelrycrafting": 3},
        inventory={"hex_wood": 5},
        skill_xp={"weaponcrafting": 0}, skill_max_xp={"weaponcrafting": 10},
    )
    return state, game_data


@pytest.fixture
def canned_sense(audit_world: tuple[object, object],
                 monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cmd, "_sense", lambda character: audit_world)


def _publish_sibling_levels(db: str, sibling: str, levels: dict[str, int]) -> None:
    """A live sibling's `SkillLedger` row, published from ITS OWN store —
    `sibling_skill_levels` excludes the reading character's own rows, so this
    must be a different character than the one under audit."""
    store = CoordinationStore(db_path=db, character=sibling)
    store.publish_skills(levels, coordination_now())


def test_the_three_counts_always_print(
    db_path: str, canned_sense: None, capsys: pytest.CaptureFixture[str],
) -> None:
    """hexstaff is ELIGIBLE (held 1 < required 10 <= sibling 10) but nothing
    has seeded `fleet_supply_request_cycles`, so `_sibling_craft_option`'s own
    pricing gate declines it — PRICED and LOAD-BEARING must both print as
    explicit zero, not be silently omitted, or a suppressed gate would read as
    "no candidates" instead of "a gate suppresses the route"."""
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})

    cmd.sibling_route_audit_command(character="C3P0")

    out = capsys.readouterr().out
    assert "1 eligible" in out
    assert "0 priced" in out
    assert "0 load-bearing" in out


def test_an_ineligible_item_is_excluded_from_the_eligible_count(
    db_path: str, canned_sense: None, capsys: pytest.CaptureFixture[str],
) -> None:
    """`already_met` names a crafting skill and a sibling holds a level for it,
    but this character's OWN held level already clears the gate — it must not
    inflate the eligible count."""
    _publish_sibling_levels(db_path, "R2D2",
                            {"weaponcrafting": 10, "jewelrycrafting": 5})

    cmd.sibling_route_audit_command(character="C3P0")

    out = capsys.readouterr().out
    assert "1 eligible" in out, "only hexstaff is eligible; already_met must not count"


def _seed_supply_request(db: str, character: str) -> None:
    """One `SupplyBank` cycle, so `fleet_supply_request_cycles()` returns a
    real, positive observation and `_sibling_craft_option`'s pricing gate is
    satisfied — the same shape the "already measured" section's 223 live
    pairs give it."""
    store = LearningStore(db, character=character)
    store.start_session()
    store.record_cycle(Cycle(
        ts="2026-09-21T00:00:00+00:00", session_id="placeholder", cycle_index=0,
        character=character, outcome="ok", selected_goal="SupplyBank(hex_wood x4)",
        root_group="trunk", actual_cooldown_seconds=10.0, delta_xp=0,
        delta_skill_xp_json="{}", delta_gold=0,
    ))
    store.end_session(exit_reason="normal")
    store.close()


def test_a_load_bearing_row_prints_its_saving(
    db_path: str, canned_sense: None, capsys: pytest.CaptureFixture[str],
) -> None:
    """With a positive `fleet_supply_request_cycles` observation, hexstaff's
    sibling route is genuinely PRICED, and because hexstaff has no other route
    at all in this world (no vendor, no drop, no known weaponcrafting
    workshop), pricing it without the sibling is strictly more expensive —
    LOAD-BEARING, with a printed, positive saving."""
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})
    _seed_supply_request(db_path, "R2D2")

    cmd.sibling_route_audit_command(character="C3P0")

    out = capsys.readouterr().out
    assert "1 eligible" in out
    assert "1 priced" in out
    assert "1 load-bearing" in out
    row = next(line for line in out.splitlines() if line.startswith("hexstaff"))
    assert "saving" in row
    # saving must be a real positive number, not a zero placeholder
    saving = int(row.split("saving")[1].split()[0])
    assert saving > 0


def test_no_real_api_call_is_reachable(
    db_path: str, canned_sense: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_sense` is the only seam that could reach the network, and this test
    replaces it — asserting `Config.from_token_file`/`ClientManager` are never
    invoked pins that no code path in the command bypasses the seam."""
    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("real API construction must not be reachable")

    monkeypatch.setattr(cmd.Config, "from_token_file", _boom)
    monkeypatch.setattr(cmd, "ClientManager", _boom)

    cmd.sibling_route_audit_command(character="C3P0")


def _sensing_player(state: object, game_data: object) -> MagicMock:
    player = MagicMock()
    player.state = state
    player.game_data = game_data
    return player


def test_sense_returns_the_players_state_and_game_data() -> None:
    """`_sense` mirrors `objective_audit_report.py`'s construction sequence:
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

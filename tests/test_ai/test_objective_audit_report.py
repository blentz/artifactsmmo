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
    assert "== currency rates (" in out
    assert "== pareto frontier ==" in out
    assert "== gated xp sources (nearest binding gate first) ==" in out


def test_every_windowed_section_prints_the_window_it_used(
    db_path: str, canned_sense: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both windowed sections state their row count, id span and time span.
    They used to be able to disagree about the era in silence — measured at
    `--window 5000`, C3P0's header covered 09-17..09-22 while one goal slice
    covered 09-12..09-17, a window that ENDED where the header's began."""
    _seed_attributed(db_path, "C3P0")

    cmd.objective_audit_command(character="C3P0", window=100)

    out = capsys.readouterr().out
    assert "== root groups (C3P0, 1 cycles, ids 1..1 · " in out
    assert "== currency rates (1 attributed rows, ids 1..1 · " in out


def test_a_character_with_no_rows_says_so_instead_of_spanning_nothing(
    db_path: str, canned_sense: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """An empty window has no id range to print. `no rows` is the honest
    statement; a fabricated span would read as a measured era."""
    _seed_attributed(db_path, "C3P0")

    cmd.objective_audit_command(character="Nobody", window=100)

    out = capsys.readouterr().out
    assert "== root groups (Nobody, 0 cycles, no rows) ==" in out
    assert "== currency rates (0 attributed rows, no rows) ==" in out


def _seed_split_history(db: str, character: str) -> None:
    """Six cycles for one character. `Grind` runs at ids 1-2 (an OLD era, paying
    a huge XP rate), `Deposit` at ids 3-4, and `Grind` again at ids 5-6 (the
    recent era, paying little). With `window=3` the report's era is ids 4..6, so
    only the two recent `Grind` rows may count — but `recent_goal_cycles` reads
    `window * 10` raw rows and caps only the OWNED result at `window`, so
    unbounded it hands back three `Grind` rows, one of them from before the
    header's window even starts."""
    store = LearningStore(db, character=character)
    store.start_session()
    plan = [("GrindCharacterXP(green_slime)", 900), ("GrindCharacterXP(green_slime)", 900),
            ("DepositInventory", 0), ("DepositInventory", 0),
            ("GrindCharacterXP(green_slime)", 10), ("GrindCharacterXP(green_slime)", 10)]
    for index, (goal, xp) in enumerate(plan):
        store.record_cycle(Cycle(
            ts=f"2026-09-2{index}T00:00:00+00:00", session_id="placeholder",
            cycle_index=index, character=character, outcome="ok", selected_goal=goal,
            root_group="trunk", actual_cooldown_seconds=10.0, delta_xp=xp,
            delta_skill_xp_json="{}", delta_gold=0,
        ))
    store.end_session(exit_reason="normal")
    store.close()


def test_goal_slices_are_clipped_to_the_headers_window(
    db_path: str, canned_sense: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """The C2 regression test. The rate census must measure the SAME era the
    header does, or the Pareto frontier compares bundles from different months.
    Unclipped, `Grind` would report 3 cycles and (900+900+10)/30 = 60.33
    char-xp/s; clipped to ids 4..6 it reports the 2 rows that are actually in
    the window, at (10+10)/20 = 1.0."""
    _seed_split_history(db_path, "C3P0")

    cmd.objective_audit_command(character="C3P0", window=3)

    out = capsys.readouterr().out
    assert "== root groups (C3P0, 3 cycles, ids 4..6 · " in out
    grind = next(line for line in out.splitlines()
                 if line.startswith("GrindCharacterXP(green_slime)"))
    assert "2 cyc" in grind
    assert "1.0000 char-xp/s" in grind


def _seed_grind_then_recovery(db: str, character: str) -> None:
    """A fight followed by the Rest it forced. `recent_goal_cycles` puts the
    Rest in the grind's slice (that is the whole point of recovery attribution)
    AND `RestoreHP` owns its own rows, so the Rest is in two slices."""
    store = LearningStore(db, character=character)
    store.start_session()
    for index, goal in enumerate(["GrindCharacterXP(green_slime)", "RestoreHP"]):
        store.record_cycle(Cycle(
            ts=f"2026-09-21T00:00:0{index}+00:00", session_id="placeholder",
            cycle_index=index, character=character, outcome="ok", selected_goal=goal,
            root_group="trunk", actual_cooldown_seconds=10.0, delta_xp=10,
            delta_skill_xp_json="{}", delta_gold=0,
        ))
    store.end_session(exit_reason="normal")
    store.close()


def test_the_rate_sections_row_count_cannot_exceed_its_window(
    db_path: str, canned_sense: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """A recovery cycle sits in two slices, so summing the slices reported more
    rows than the window holds — 5,714 over a 5,000-row window on C3P0's first
    run under this header. Counting distinct cycles is the fix; a section that
    can overstate its own window is the defect this header exists to prevent."""
    _seed_grind_then_recovery(db_path, "C3P0")

    cmd.objective_audit_command(character="C3P0", window=100)

    out = capsys.readouterr().out
    assert "== root groups (C3P0, 2 cycles, " in out
    assert "== currency rates (2 attributed rows, " in out
    # And the recovery slice itself is still refused as a bundle: it appears in
    # the caveat line and nowhere as a measured row.
    assert not [line for line in out.splitlines()
                if line.startswith("RestoreHP") and " cyc " in line]


def test_the_reports_caveats_are_printed_not_left_to_the_docstring(
    db_path: str, canned_sense: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """Three things a reader would otherwise have to already know: recovery is
    excluded from the bundles, the frontier does not weight by sample size, and
    the gold axis is gross. All three changed a live reading of this report."""
    _seed_attributed(db_path, "C3P0")

    cmd.objective_audit_command(character="C3P0", window=100)

    out = capsys.readouterr().out
    assert "RestoreHP is excluded" in out
    assert "n is unweighted; gold is gross" in out


def test_the_frontier_prints_its_sample_size(
    db_path: str, canned_sense: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """`CraftRelief(apple_pie)` reached the live frontier on 3 cycles / 34.7 s
    at 50.98 skill-xp/s, beside a 5,000-cycle bundle, with nothing marking the
    difference. Domination is a comparison of rates alone, so n has to be on
    the line."""
    _seed_attributed(db_path, "C3P0")

    cmd.objective_audit_command(character="C3P0", window=100)

    out = capsys.readouterr().out
    frontier_section = out.split("== pareto frontier ==")[1]
    assert "1 cyc" in frontier_section


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
    """The catalogue calibrated in `test_xp_gate_census.py`'s module docstring,
    reproduced here rather than imported: that module warns (per
    `feedback_scenario_declares_its_world`) that a shared `GameData` fixture
    answering a different question is how three vacuous measurements and one
    false retraction got shipped, and this file asks about PRINTING, not about
    the chains.

    Its measured shape, with the character at weaponcrafting 1 / gearcrafting 0:
    `troll` has TWO gates — `leather_vest` (gearcrafting 0->1, gap 1) and its
    binding `copper_axe` (weaponcrafting 1->3, gap 2) — `dragon` has the single
    `copper_axe` gate, and `wolf` has `iron_sword` (weaponcrafting 1->20, gap
    19). That is the world in which the command must print a binding line AND
    an `also needs` line under the monster they belong to, instead of letting
    the shallow step compete for a slot in the top 20."""
    game_data = GameData()
    game_data._item_stats = {
        "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon",
                                  attack={"air": 2}),
        "leather_vest": ItemStats(code="leather_vest", level=1, type_="body_armor",
                                  resistance={"water": 90},
                                  crafting_skill="gearcrafting", crafting_level=1),
        "iron_sword": ItemStats(code="iron_sword", level=1, type_="weapon",
                                attack={"water": 40},
                                crafting_skill="weaponcrafting", crafting_level=20),
        "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                attack={"fire": 6},
                                crafting_skill="weaponcrafting", crafting_level=3),
        "found_shield": ItemStats(code="found_shield", level=1, type_="shield",
                                  resistance={"earth": 90}),
    }
    game_data._monster_level = {"green_slime": 1, "troll": 2, "wolf": 3,
                                "dragon": 4, "hydra": 40}
    game_data._monster_hp = {"green_slime": 1, "troll": 80, "wolf": 200,
                             "dragon": 80, "hydra": 5000}
    game_data._monster_attack = {
        "green_slime": {}, "troll": {"water": 40}, "wolf": {"air": 12},
        "dragon": {"earth": 40},
        "hydra": {"fire": 200, "water": 200, "earth": 200, "air": 200},
    }
    game_data._monster_resistance = {
        "green_slime": {}, "troll": {"water": 100, "fire": 0},
        "wolf": {"fire": 100, "water": 0}, "dragon": {"fire": 0, "water": 100},
        "hydra": {"fire": 100, "water": 100, "earth": 100, "air": 100},
    }
    fill_monster_stat_defaults(game_data)
    state = make_state(level=5, hp=150, max_hp=150, equipment={},
                       inventory={"wooden_stick": 1},
                       skills={"weaponcrafting": 1, "gearcrafting": 0})
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
    assert "gap 19 binds on iron_sword (weapon) · weaponcrafting 1->20" in out


def test_a_monsters_shallow_step_prints_under_it_not_as_a_peer(
    db_path: str, gated_world: tuple[object, object],
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """troll needs gearcrafting +1 AND weaponcrafting +2, so it costs +2. The
    report must head troll's entry with the BINDING gate and list the +1 step
    underneath — the shallow step is part of the same bill, not a cheaper
    fight, and letting it be its own row put it above monsters that really are
    nearer and let the `[:20]` cut drop the step that binds."""
    _seed_attributed(db_path, "C3P0")
    monkeypatch.setattr(cmd, "_sense", lambda character: gated_world)

    cmd.objective_audit_command(character="C3P0", window=100)

    out = capsys.readouterr().out
    assert "troll" in out
    assert "gap  2 binds on copper_axe (weapon) · weaponcrafting 1->3" in out
    assert "also needs leather_vest (body_armor) · gearcrafting 0->1 (gap 1)" in out
    # The gate list is a monster ranking, so each monster appears exactly once.
    heads = [line.split()[0] for line in out.splitlines()
             if " binds on " in line]
    assert heads == ["dragon", "troll", "wolf"]

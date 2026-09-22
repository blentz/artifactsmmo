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

from dataclasses import replace
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
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.audit.sibling_route_census import SiblingVerdict
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
    """`_sense` now returns a THIRD element, the player's `_last_ctx`
    (I2) — every test that only cares about the world's state/game_data
    passes `NO_PROFILE_CONTEXT` here unchanged; the tests that pin I2 itself
    build their own marker context instead of going through this fixture."""
    monkeypatch.setattr(cmd, "_sense", lambda character: (*audit_world, NO_PROFILE_CONTEXT))


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


def test_a_crafting_skill_with_no_recipe_is_excluded_from_eligible(
    db_path: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """`_eligible_candidates` must match `sibling_route_verdicts`'s own skip
    condition (recipe is None) exactly, not just the `crafting_skill` half of
    it. `no_recipe_ring` names a crafting skill a sibling clears but has no
    entry in `crafting_recipes` -- the census would silently skip it (emit no
    verdict), so it must not inflate `eligible` here or the
    priced/load-bearing counts (derived from the verdicts the census DID
    emit) would be measured against a denominator the census never saw."""
    game_data = GameData(
        items=ItemCatalog(stats={
            "no_recipe_ring": ItemStats(code="no_recipe_ring", level=1, type_="ring",
                                        crafting_skill="jewelrycrafting",
                                        crafting_level=1),
        }),
        recipes_catalog=RecipeCatalog(crafting_recipes={}, craft_yields={}),
    )
    state = make_state(skills={**_ALL_SKILLS, "jewelrycrafting": 1})
    monkeypatch.setattr(cmd, "_sense",
                        lambda character: (state, game_data, NO_PROFILE_CONTEXT))
    _publish_sibling_levels(db_path, "R2D2", {"jewelrycrafting": 10})

    cmd.sibling_route_audit_command(character="C3P0")

    out = capsys.readouterr().out
    assert "0 eligible" in out, "no_recipe_ring names a skill but has no recipe"


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
    LOAD-BEARING, with a printed, positive saving. Rows print grouped by GATE
    (I1), so the line is keyed on the skill, with the item named inside it."""
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})
    _seed_supply_request(db_path, "R2D2")

    cmd.sibling_route_audit_command(character="C3P0")

    out = capsys.readouterr().out
    assert "1 eligible" in out
    assert "1 priced" in out
    assert "1 load-bearing" in out
    assert "savings are priced off a live-updating skill_grind_rate" in out, \
        "the drift caveat must accompany the load-bearing rows"
    row = next(line for line in out.splitlines() if line.startswith("weaponcrafting"))
    assert "hexstaff" in row
    assert "saving" in row
    # saving must be a real positive number, not a zero placeholder
    saving = int(row.split("saving")[1].split()[0])
    assert saving > 0


def test_header_prints_the_pricing_scalar_and_the_priced_caveat(
    db_path: str, canned_sense: None, capsys: pytest.CaptureFixture[str],
) -> None:
    """`priced` is structurally either 0 or equal to `eligible`: the ONLY gate
    `_sibling_craft_option` applies is `store.fleet_supply_request_cycles()`,
    one scalar read once per run and applied identically to every eligible
    item. The header must print that raw scalar and the caveat explaining
    why `priced == eligible` is the expected case, not N independent
    confirmations -- otherwise "N priced" misleadingly reads as per-route
    evidence."""
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})
    _seed_supply_request(db_path, "R2D2")

    cmd.sibling_route_audit_command(character="C3P0")

    out = capsys.readouterr().out
    assert "fleet_supply_request_cycles: 1.0" in out
    assert "priced can only diverge from eligible when fleet_supply_request_cycles" in out


def test_header_prints_none_when_the_fleet_has_never_served_a_request(
    db_path: str, canned_sense: None, capsys: pytest.CaptureFixture[str],
) -> None:
    """No `SupplyBank` cycle anywhere in the store -> the scalar itself is
    `None`, and the header must print that literally rather than a blank or
    a zero that would misrepresent "never observed" as "observed at zero"."""
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})

    cmd.sibling_route_audit_command(character="C3P0")

    out = capsys.readouterr().out
    assert "fleet_supply_request_cycles: None" in out
    assert "0 priced" in out


def test_header_states_that_counts_drift_too_not_only_savings(
    db_path: str, canned_sense: None, capsys: pytest.CaptureFixture[str],
) -> None:
    """M3: the existing drift note only warned that SAVINGS drift between
    runs; the eligible/priced/load-bearing COUNTS drift too, because they are
    read off this character's own live skill levels — an item leaves the
    eligible set the moment the character clears its gate. The header must
    say so as well, not just the savings caveat."""
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})

    cmd.sibling_route_audit_command(character="C3P0")

    out = capsys.readouterr().out
    assert "these counts drift between runs too" in out
    assert "live skills" in out


def test_command_prices_with_the_players_real_context_not_no_profile(
    db_path: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """I2: the command must price every route with `player._last_ctx`
    (overriding only `sibling_skills`), not `NO_PROFILE_CONTEXT` -- the
    stand-in's own docstring says it "is NOT a substitute for the player's
    real context". Pinned by giving `_sense` a marker context that diverges
    from `NO_PROFILE_CONTEXT` in a field the stand-in hard-codes
    (`bank_accessible=True`), then asserting the census actually receives
    that marker (not the hard-coded default) with only `sibling_skills`
    overridden on top."""
    state = make_state(skills=_ALL_SKILLS)
    game_data = GameData()
    marker_ctx = replace(NO_PROFILE_CONTEXT, bank_accessible=False)
    monkeypatch.setattr(cmd, "_sense", lambda character: (state, game_data, marker_ctx))
    monkeypatch.setattr(cmd, "_eligible_candidates", lambda *a, **k: [])

    captured: dict[str, object] = {}

    def _capture_ctx(state_, game_data_, ctx, store, items):
        captured["ctx"] = ctx
        return []

    monkeypatch.setattr(cmd, "sibling_route_verdicts", _capture_ctx)
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})

    cmd.sibling_route_audit_command(character="C3P0")

    ctx = captured["ctx"]
    assert ctx.bank_accessible is False, (
        "the command must price with the player's real _last_ctx, not "
        "NO_PROFILE_CONTEXT, which hard-codes bank_accessible=True"
    )
    assert ctx.sibling_skills == {"weaponcrafting": 10}, (
        "sibling_skills must still be overridden with the coordination "
        "store's read, on top of the player's own (empty) copy"
    )


def _verdict(item: str, skill: str = "jewelrycrafting", required_level: int = 15,
            held_level: int = 1, best_sibling_level: int = 15,
            actions_with: int = 8, actions_without: int = 40) -> SiblingVerdict:
    return SiblingVerdict(item=item, skill=skill, required_level=required_level,
                          held_level=held_level, best_sibling_level=best_sibling_level,
                          priced=True, actions_with=actions_with,
                          actions_without=actions_without)


def test_group_by_gate_collapses_two_items_behind_the_same_gate() -> None:
    """I1: two items sharing `(skill, required_level)` must collapse into ONE
    gate group, not two -- the pin the finding asked for by name."""
    gates = cmd._group_by_gate([_verdict("ring_a"), _verdict("ring_b")])

    assert len(gates) == 1
    skill, level, members = gates[0]
    assert (skill, level) == ("jewelrycrafting", 15)
    assert {m.item for m in members} == {"ring_a", "ring_b"}


def test_group_by_gate_keeps_different_gates_separate() -> None:
    """Different skills, or the same skill at a different required level, are
    different gates and must not collapse together."""
    same_skill_other_level = _verdict("ring_c", required_level=20)
    other_skill = _verdict("hexstaff", skill="weaponcrafting", required_level=10)

    gates = cmd._group_by_gate([_verdict("ring_a"), same_skill_other_level, other_skill])

    assert len(gates) == 3


def test_group_by_gate_sorts_largest_saving_first() -> None:
    small = _verdict("ring_small", skill="cooking", required_level=5,
                     actions_with=9, actions_without=10)  # saving 1
    big = _verdict("ring_big", skill="alchemy", required_level=5,
                   actions_with=1, actions_without=100)  # saving 99

    gates = cmd._group_by_gate([small, big])

    assert [skill for skill, _, _ in gates] == ["alchemy", "cooking"]


def test_print_gate_line_prints_the_saving_once_not_per_item(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """I1's own proof: six identical-saving rows must not become six printed
    numbers a reader could sum. One gate, one saving, both items named."""
    v1 = _verdict("ring_a", actions_with=8, actions_without=40)  # saving 32
    v2 = _verdict("ring_b", actions_with=8, actions_without=40)  # saving 32

    cmd._print_gate_line("jewelrycrafting", 15, [v1, v2])

    out = capsys.readouterr().out
    assert out.count("saving") == 1
    assert "saving 32" in out
    assert "ring_a" in out and "ring_b" in out
    assert "2 item(s)" in out


def test_print_gate_line_shows_a_range_when_savings_genuinely_diverge(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Nothing GUARANTEES every item behind a gate reports the identical
    saving (that is an observed fact about live data, not a pricer
    invariant), so a divergent group must print honestly rather than
    silently picking one member's number."""
    v1 = _verdict("ring_a", actions_with=8, actions_without=40)   # saving 32
    v2 = _verdict("ring_b", actions_with=10, actions_without=40)  # saving 30

    cmd._print_gate_line("jewelrycrafting", 15, [v1, v2])

    out = capsys.readouterr().out
    assert "saving 30-32" in out
    assert "varies within this gate" in out


def test_two_items_behind_the_same_gate_produce_one_gate_line_end_to_end(
    db_path: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """I1, end to end through the real command: two items behind the same
    gate (jewelrycrafting 15), both load-bearing, must print as ONE line in
    the load-bearing section, not two."""
    game_data = GameData(
        items=ItemCatalog(stats={
            "ring_a": ItemStats(code="ring_a", level=15, type_="ring",
                                crafting_skill="jewelrycrafting", crafting_level=15),
            "ring_b": ItemStats(code="ring_b", level=15, type_="ring",
                                crafting_skill="jewelrycrafting", crafting_level=15),
            "ring_wood": ItemStats(code="ring_wood", level=1, type_="resource"),
        }),
        recipes_catalog=RecipeCatalog(
            crafting_recipes={"ring_a": {"ring_wood": 1}, "ring_b": {"ring_wood": 1}},
            craft_yields={"ring_a": 1, "ring_b": 1},
        ),
    )
    state = make_state(
        skills={**_ALL_SKILLS, "jewelrycrafting": 1},
        inventory={"ring_wood": 5},
        skill_xp={"jewelrycrafting": 0}, skill_max_xp={"jewelrycrafting": 10},
    )
    monkeypatch.setattr(cmd, "_sense", lambda character: (state, game_data, NO_PROFILE_CONTEXT))
    _publish_sibling_levels(db_path, "R2D2", {"jewelrycrafting": 15})
    _seed_supply_request(db_path, "R2D2")

    cmd.sibling_route_audit_command(character="C3P0")

    out = capsys.readouterr().out
    gate_lines = [line for line in out.splitlines() if line.startswith("jewelrycrafting")]
    assert len(gate_lines) == 1, f"expected exactly one gate line, got {gate_lines}"
    assert "ring_a" in gate_lines[0] and "ring_b" in gate_lines[0]
    assert "2 item(s)" in gate_lines[0]
    assert "2 load-bearing (1 gate(s))" in out
    assert "NOT additive across the listed items" in out


def test_outpriced_rows_print_in_their_own_section(
    db_path: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """M1: a verdict that is PRICED but not LOAD-BEARING (saving <= 0, some
    existing route already undercuts the sibling craft) must print in its own
    section -- `sibling_route_census.py`'s docstring calls distinguishing
    "outpriced" from "absent" the entire point of keeping `priced` and
    `load_bearing` separate, and a report that only showed load-bearing rows
    made that distinction unreadable by omission."""
    state = make_state(skills=_ALL_SKILLS)
    game_data = GameData(
        items=ItemCatalog(stats={
            "outpriced_ring": ItemStats(code="outpriced_ring", level=1, type_="ring",
                                        crafting_skill="jewelrycrafting",
                                        crafting_level=15),
        }),
        recipes_catalog=RecipeCatalog(
            crafting_recipes={"outpriced_ring": {}}, craft_yields={"outpriced_ring": 1}),
    )
    monkeypatch.setattr(cmd, "_sense",
                        lambda character: (state, game_data, NO_PROFILE_CONTEXT))
    monkeypatch.setattr(cmd, "_eligible_candidates", lambda *a, **k: ["outpriced_ring"])
    outpriced_verdict = SiblingVerdict(
        item="outpriced_ring", skill="jewelrycrafting", required_level=15,
        held_level=1, best_sibling_level=15, priced=True,
        actions_with=10, actions_without=10)
    monkeypatch.setattr(cmd, "sibling_route_verdicts",
                        lambda *a, **k: [outpriced_verdict])
    _publish_sibling_levels(db_path, "R2D2", {"jewelrycrafting": 15})

    cmd.sibling_route_audit_command(character="C3P0")

    out = capsys.readouterr().out
    assert "1 priced" in out
    assert "0 load-bearing" in out
    assert "priced but not load-bearing" in out
    row = next(line for line in out.splitlines() if line.startswith("outpriced_ring"))
    assert "priced but not cheaper" in row


def test_no_outpriced_section_when_nothing_is_outpriced(
    db_path: str, canned_sense: None, capsys: pytest.CaptureFixture[str],
) -> None:
    """A run with no priced-but-not-load-bearing items must not print the
    empty section header -- same discipline as the eligible/priced/
    load-bearing counts, which print unconditionally, versus the sectioned
    rows, which only print when there is something to show."""
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})

    cmd.sibling_route_audit_command(character="C3P0")

    out = capsys.readouterr().out
    assert "priced but not load-bearing" not in out


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


def _sensing_player(state: object, game_data: object, ctx: object = None) -> MagicMock:
    player = MagicMock()
    player.state = state
    player.game_data = game_data
    # `plan_once()` -> `plan_from_state()` sets `self._last_ctx` as a side
    # effect (`player.py:1087`); this mock stands in for that assignment
    # having already happened by the time `_sense` reads it.
    player._last_ctx = ctx if ctx is not None else NO_PROFILE_CONTEXT
    return player


def test_sense_returns_the_players_state_game_data_and_last_ctx() -> None:
    """`_sense` mirrors `objective_audit_report.py`'s construction sequence:
    Config -> ClientManager -> an in-memory LearningStore -> GamePlayer.plan_once().
    Config/ClientManager/GamePlayer are substituted so this never touches the
    real token file, API client or network.

    I2: `_sense` must also return `player._last_ctx` — the context
    `plan_from_state` actually built for this cycle — not the
    `NO_PROFILE_CONTEXT` stand-in the command used to price against. The
    marker context here differs from `NO_PROFILE_CONTEXT` in a field the
    stand-in hard-codes (`bank_accessible`), so returning the wrong object
    would be visible by identity AND by value."""
    state = make_state(level=5)
    game_data = GameData()
    marker_ctx = replace(NO_PROFILE_CONTEXT, bank_accessible=False)
    player = _sensing_player(state, game_data, marker_ctx)
    with (
        patch.object(cmd.Config, "from_token_file",
                     return_value=MagicMock(game_data_ttl_minutes=5)),
        patch.object(cmd, "ClientManager"),
        patch.object(cmd, "GamePlayer", return_value=player),
    ):
        result_state, result_game_data, result_ctx = cmd._sense("C3P0")

    assert result_state is state
    assert result_game_data is game_data
    assert result_ctx is marker_ctx
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

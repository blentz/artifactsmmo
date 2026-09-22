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
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.audit.root_sibling_census import BlockedTargetVerdict, RootSiblingVerdict
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
    """`_sense` now returns a THIRD and FOURTH element, the player's
    `_last_ctx` (I2) and `_objective` (T2.1) — every test that only cares
    about the world's state/game_data passes `NO_PROFILE_CONTEXT` and this
    world's own `CharacterObjective` here unchanged; the tests that pin I2
    itself build their own marker context instead of going through this
    fixture.

    ALSO stubs `cmd.root_sibling_verdicts` to an empty list. The T2.1
    section this stub feeds is not what these T2.0-era tests are pinning —
    driving the REAL `resolve_root` walk over this module's deliberately
    minimal, hand-built world (see `audit_world`'s own docstring) is a
    different module's job (`test_root_sibling_census.py`, and
    `test_decisions_root.py` for the walk itself); tests that DO care about
    the root section substitute this stub with their own controlled rows
    instead."""
    state, game_data = audit_world
    objective = CharacterObjective.from_game_data(game_data)
    monkeypatch.setattr(
        cmd, "_sense",
        lambda character: (state, game_data, NO_PROFILE_CONTEXT, objective))
    monkeypatch.setattr(cmd, "root_sibling_verdicts", lambda *a, **k: ([], None))


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

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

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

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

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
    objective = CharacterObjective.from_game_data(game_data)
    monkeypatch.setattr(
        cmd, "_sense",
        lambda character: (state, game_data, NO_PROFILE_CONTEXT, objective))
    monkeypatch.setattr(cmd, "root_sibling_verdicts", lambda *a, **k: ([], None))
    _publish_sibling_levels(db_path, "R2D2", {"jewelrycrafting": 10})

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

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

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

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

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

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

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

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

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

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
    objective = CharacterObjective.from_game_data(game_data)
    monkeypatch.setattr(
        cmd, "_sense", lambda character: (state, game_data, marker_ctx, objective))
    monkeypatch.setattr(cmd, "_eligible_candidates", lambda *a, **k: [])
    monkeypatch.setattr(cmd, "root_sibling_verdicts", lambda *a, **k: ([], None))

    captured: dict[str, object] = {}

    def _capture_ctx(state_, game_data_, ctx, store, items):
        captured["ctx"] = ctx
        return []

    monkeypatch.setattr(cmd, "sibling_route_verdicts", _capture_ctx)
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

    ctx = captured["ctx"]
    assert ctx.bank_accessible is False, (
        "the command must price with the player's real _last_ctx, not "
        "NO_PROFILE_CONTEXT, which hard-codes bank_accessible=True"
    )
    assert ctx.sibling_skills == {"weaponcrafting": 10}, (
        "sibling_skills must still be overridden with the coordination "
        "store's read, on top of the player's own (empty) copy"
    )


def test_root_section_is_driven_with_the_sensed_objective_and_the_augmented_ctx(
    db_path: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """I1: the Task-1/Task-2 seam (`_print_root_section`'s call to
    `root_sibling_verdicts` at the end of `_run_for_character`) had no test
    capturing its arguments. A mutant that passed a freshly built
    `CharacterObjective.from_game_data(game_data)` in place of the sensed
    `objective`, and `player_ctx` (whose `sibling_skills` is EMPTY) in place
    of the augmented `ctx`, printed the IDENTICAL "0 sibling-priced / 0
    load-bearing" every correct run also prints -- `_sibling_craft_option`
    declines at its third guard for every item once `sibling_skills` is
    empty, so the mutant is silent. All 32 pre-existing tests passed under
    that mutation.

    Pinned the same way T2.0's own seam test
    (`test_command_prices_with_the_players_real_context_not_no_profile`)
    pins `sibling_route_verdicts`' ctx: capture the arguments
    `root_sibling_verdicts` is actually called with and assert against the
    sensed objects, not the report's printed counts (a broken seam can print
    the same counts by coincidence, but it cannot fake object identity or a
    ctx.sibling_skills that only the coordination-store read produces)."""
    state = make_state(skills=_ALL_SKILLS)
    game_data = GameData()
    marker_ctx = replace(NO_PROFILE_CONTEXT, bank_accessible=False)
    sensed_objective = CharacterObjective.from_game_data(game_data)
    monkeypatch.setattr(
        cmd, "_sense",
        lambda character: (state, game_data, marker_ctx, sensed_objective))
    monkeypatch.setattr(cmd, "_eligible_candidates", lambda *a, **k: [])
    monkeypatch.setattr(cmd, "sibling_route_verdicts", lambda *a, **k: [])

    captured: dict[str, object] = {}

    def _capture_root_args(state_, game_data_, objective, ctx, store):
        captured["objective"] = objective
        captured["ctx"] = ctx
        return [], None

    monkeypatch.setattr(cmd, "root_sibling_verdicts", _capture_root_args)
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

    assert captured["objective"] is sensed_objective, (
        "root_sibling_verdicts must be driven with the SAME CharacterObjective "
        "_sense returned, not a freshly built CharacterObjective.from_game_data"
    )
    root_ctx = captured["ctx"]
    assert root_ctx.sibling_skills == {"weaponcrafting": 10}, (
        "root_sibling_verdicts must receive the ctx AUGMENTED with the real "
        "coordination-store read, not the player's own (empty) sibling_skills"
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
    objective = CharacterObjective.from_game_data(game_data)
    monkeypatch.setattr(
        cmd, "_sense",
        lambda character: (state, game_data, NO_PROFILE_CONTEXT, objective))
    monkeypatch.setattr(cmd, "root_sibling_verdicts", lambda *a, **k: ([], None))
    _publish_sibling_levels(db_path, "R2D2", {"jewelrycrafting": 15})
    _seed_supply_request(db_path, "R2D2")

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

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
    objective = CharacterObjective.from_game_data(game_data)
    monkeypatch.setattr(
        cmd, "_sense",
        lambda character: (state, game_data, NO_PROFILE_CONTEXT, objective))
    monkeypatch.setattr(cmd, "_eligible_candidates", lambda *a, **k: ["outpriced_ring"])
    outpriced_verdict = SiblingVerdict(
        item="outpriced_ring", skill="jewelrycrafting", required_level=15,
        held_level=1, best_sibling_level=15, priced=True,
        actions_with=10, actions_without=10)
    monkeypatch.setattr(cmd, "sibling_route_verdicts",
                        lambda *a, **k: [outpriced_verdict])
    monkeypatch.setattr(cmd, "root_sibling_verdicts", lambda *a, **k: ([], None))
    _publish_sibling_levels(db_path, "R2D2", {"jewelrycrafting": 15})

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

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

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

    out = capsys.readouterr().out
    assert "priced but not load-bearing" not in out


def _root_verdict(root_repr: str, item: str | None = None, chosen: bool = False,
                  verdict: SiblingVerdict | None = None) -> RootSiblingVerdict:
    return RootSiblingVerdict(root_repr=root_repr, item=item, chosen=chosen, verdict=verdict)


def test_root_section_qualifier_states_scope(
    db_path: str, canned_sense: None, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The root section's qualifier must state that it prices each root's own
    item only and does not walk the acquisition plan — a zero count means no
    chosen root is itself sibling-craftable, not that a sibling cannot help
    supply its materials."""
    rows = [_root_verdict("ObtainItem(code='hexstaff')", item="hexstaff",
                          chosen=True)]
    monkeypatch.setattr(cmd, "root_sibling_verdicts", lambda *a, **k: (rows, None))
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

    out = capsys.readouterr().out
    assert "this section prices each root's OWN item only and does not walk the " \
        "root's acquisition plan" in out
    assert "a zero count means no chosen root is itself sibling-craftable" in out


def test_root_section_prints_all_four_counts_and_the_chosen_row(
    db_path: str, canned_sense: None, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """T2.1: the root section must print all four counts (candidates, named,
    sibling-priced, load-bearing) and the chosen root's line, when the chosen
    root itself names an item that IS sibling-priced and load-bearing."""
    chosen_verdict = _verdict("hexstaff", skill="weaponcrafting", required_level=10,
                              actions_with=4, actions_without=40)  # priced, load-bearing
    other = _root_verdict("ReachCharLevel(2)")
    rows = [
        _root_verdict("ObtainItem(code='hexstaff')", item="hexstaff",
                      chosen=True, verdict=chosen_verdict),
        other,
    ]
    monkeypatch.setattr(cmd, "root_sibling_verdicts", lambda *a, **k: (rows, None))
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

    out = capsys.readouterr().out
    assert "== root-sibling audit (C3P0) ==" in out
    assert "2 candidate root(s)" in out
    assert "1 name an item" in out
    assert "1 sibling-priced" in out
    assert "1 load-bearing" in out
    assert "chosen root: ObtainItem(code='hexstaff')" in out
    assert "chosen root names item: hexstaff" in out
    assert "chosen root sibling-priced: True" in out
    assert "chosen root load-bearing: True" in out


def test_root_section_prints_explicit_zeros_when_nothing_is_priced(
    db_path: str, canned_sense: None, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A root-level count of 0 sibling-priced/load-bearing roots is a real
    and likely answer -- the walk may simply never name an item behind a
    sibling-clearable gate -- and must print as an explicit 0, not be
    omitted the way T2.0's catalogue-level report was found to read as
    evidence while being a tautology."""
    unpriced_verdict = SiblingVerdict(
        item="hexstaff", skill="weaponcrafting", required_level=10, held_level=1,
        best_sibling_level=10, priced=False, actions_with=40, actions_without=40)
    rows = [_root_verdict("ObtainItem(code='hexstaff')", item="hexstaff",
                          chosen=True, verdict=unpriced_verdict)]
    monkeypatch.setattr(cmd, "root_sibling_verdicts", lambda *a, **k: (rows, None))
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

    out = capsys.readouterr().out
    assert "1 candidate root(s)" in out
    assert "1 name an item" in out
    assert "0 sibling-priced" in out
    assert "0 load-bearing" in out
    assert "chosen root sibling-priced: False" in out
    assert "chosen root load-bearing: False" in out


def test_root_section_chosen_root_names_no_item(
    db_path: str, canned_sense: None, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A chosen root that names no item (`ReachCharLevel`/`ReachSkillLevel`)
    must print its repr and state explicitly that the sibling route could
    not apply this cycle -- a different finding from priced-then-outpriced,
    and the section header must state that distinction too."""
    rows = [_root_verdict("ReachCharLevel(char_level=6)", chosen=True)]
    monkeypatch.setattr(cmd, "root_sibling_verdicts", lambda *a, **k: (rows, None))
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

    out = capsys.readouterr().out
    assert "1 candidate root(s)" in out
    assert "0 name an item" in out
    assert "0 sibling-priced" in out
    assert "0 load-bearing" in out
    assert "chosen root: ReachCharLevel(char_level=6)" in out
    assert "chosen root names no item -- the sibling route could not apply this cycle" in out
    assert "COULD NOT APPLY this cycle -- that is a different finding from the " \
        "route being priced and then outpriced" in out
    assert "chosen root names item" not in out


def test_root_section_no_root_resolved(
    db_path: str, canned_sense: None, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`resolve_root` can return `root=None` (the `CanIClearMyTier` wall
    case); no row is `chosen=True` then, and the section must say so
    explicitly rather than silently printing nothing."""
    rows = [_root_verdict("ReachCharLevel(char_level=6)", chosen=False)]
    monkeypatch.setattr(cmd, "root_sibling_verdicts", lambda *a, **k: (rows, None))
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

    out = capsys.readouterr().out
    assert "chosen root: None (resolve_root returned no root this cycle" in out


def test_root_section_distinguishes_not_craftable_from_craftable_but_declined(
    db_path: str, canned_sense: None, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """I2: "0 sibling-priced" must not read as "measured and declined" when
    the named item was never craftable at all. `sibling_route_verdicts`
    silently skips any item with no recipe or no `crafting_skill` BEFORE it
    computes a verdict at all (`verdict=None`, outcome 2 of `root_sibling_
    census.py`'s own docstring) -- a different fact from a verdict that WAS
    computed and came back `priced=False` (outcome 3, declined). Live, this
    is EVERY named row on the fleet (all 16 item-naming roots have
    `crafting_skill=None`), so collapsing the two into one zero is not an
    academic distinction.

    Two not-craftable rows and one craftable-but-declined row must print as
    "2 name an item that is not craftable at all" and "0 sibling-priced"
    separately, not as one undifferentiated zero."""
    declined_verdict = SiblingVerdict(
        item="declined_ring", skill="jewelrycrafting", required_level=15,
        held_level=1, best_sibling_level=15, priced=False,
        actions_with=40, actions_without=40)
    rows = [
        _root_verdict("ObtainItem(code='not_craftable_a')", item="not_craftable_a",
                      chosen=True, verdict=None),
        _root_verdict("ObtainItem(code='not_craftable_b')", item="not_craftable_b",
                      verdict=None),
        _root_verdict("ObtainItem(code='declined_ring')", item="declined_ring",
                      verdict=declined_verdict),
    ]
    monkeypatch.setattr(cmd, "root_sibling_verdicts", lambda *a, **k: (rows, None))
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

    out = capsys.readouterr().out
    assert "3 candidate root(s)" in out
    assert "3 name an item" in out
    assert "2 name an item that is not craftable at all" in out
    assert "0 sibling-priced" in out
    assert "0 load-bearing" in out
    assert "chosen root item craftable at all: False" in out
    assert "chosen root item is not craftable at all" in out
    assert "chosen root sibling-priced" not in out, \
        "a chosen root with verdict=None must not print a priced/load-bearing line at all"


def test_root_section_prints_blocked_target_priced_and_load_bearing(
    db_path: str, canned_sense: None, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """I3: `resolution.blocked_target` -- the item `IsThisTargetBlocked`
    erased when it rewrote a skill-gated gear target into the chosen
    `ReachSkillLevel` root -- must print on its own line, separate from the
    candidate counts above. This is the live Lor shape: chosen root
    `ReachSkillLevel(weaponcrafting, 13)` names no item at all (0 candidates
    name an item), yet the walk DID want `elderwood_staff` before the skill
    gate converted it away, and that fact must not be lost."""
    rows = [_root_verdict("ReachSkillLevel(weaponcrafting, 13)", chosen=True)]
    blocked_verdict = _verdict("elderwood_staff", skill="weaponcrafting",
                               required_level=13, actions_with=4, actions_without=40)
    blocked = BlockedTargetVerdict(item="elderwood_staff", verdict=blocked_verdict)
    monkeypatch.setattr(cmd, "root_sibling_verdicts", lambda *a, **k: (rows, blocked))
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

    out = capsys.readouterr().out
    assert "1 candidate root(s)" in out
    assert "0 name an item" in out, "the candidate rows must not surface the erased item"
    assert "blocked_target: elderwood_staff" in out
    assert "blocked_target sibling-priced: True" in out
    assert "blocked_target load-bearing: True" in out


def test_root_section_prints_blocked_target_not_craftable(
    db_path: str, canned_sense: None, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """I3, the not-craftable case: a `blocked_target` whose item has no
    recipe or no `crafting_skill` must print as "not craftable at all", the
    same distinction I2 draws for the candidate rows, not a silently-false
    "sibling-priced: False"."""
    rows = [_root_verdict("ReachSkillLevel(mining, 20)", chosen=True)]
    blocked = BlockedTargetVerdict(item="lost_world_map", verdict=None)
    monkeypatch.setattr(cmd, "root_sibling_verdicts", lambda *a, **k: (rows, blocked))
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

    out = capsys.readouterr().out
    assert "blocked_target: lost_world_map" in out
    assert "blocked_target not craftable at all" in out
    assert "blocked_target sibling-priced" not in out


def test_root_section_prints_blocked_target_none_when_unset(
    db_path: str, canned_sense: None, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """I3, the unset case: `resolution.blocked_target` is `None` on most live
    cycles -- the walk did not convert a gear target this time -- and the
    report must say so explicitly rather than omitting the line."""
    rows = [_root_verdict("ObtainItem(code='hexstaff')", item="hexstaff", chosen=True)]
    monkeypatch.setattr(cmd, "root_sibling_verdicts", lambda *a, **k: (rows, None))
    _publish_sibling_levels(db_path, "R2D2", {"weaponcrafting": 10})

    cmd.sibling_route_audit_command(character="C3P0", characters=[])

    out = capsys.readouterr().out
    assert "blocked_target: None (this cycle's walk was not converted from a " \
        "skill-gated gear target" in out


def test_repeated_character_option_audits_each_character_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--character/-c is repeatable; every name passed must be audited,
    in order, exactly once each -- the substitute for a --all flag this
    command deliberately does not have (see the module docstring)."""
    seen: list[str] = []
    monkeypatch.setattr(cmd, "_run_for_character", seen.append)

    cmd.sibling_route_audit_command(character=None, characters=["C3P0", "R2D2"])

    assert seen == ["C3P0", "R2D2"]


def test_positional_character_and_repeated_option_combine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The legacy positional argument still names a character, and combines
    with any `--character`/`-c` options passed alongside it rather than one
    silently winning over the other."""
    seen: list[str] = []
    monkeypatch.setattr(cmd, "_run_for_character", seen.append)

    cmd.sibling_route_audit_command(character="HAL", characters=["C3P0", "R2D2"])

    assert seen == ["C3P0", "R2D2", "HAL"]


def test_no_character_named_at_all_exits_with_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Naming zero characters (no positional, no --character) must fail
    loudly with a usage error, not silently audit nothing."""
    called = False

    def _boom(character: str) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(cmd, "_run_for_character", _boom)

    with pytest.raises(typer.Exit) as exc_info:
        cmd.sibling_route_audit_command(character=None, characters=[])

    assert exc_info.value.exit_code == 2
    assert not called


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

    cmd.sibling_route_audit_command(character="C3P0", characters=[])


_UNSET = object()


def _sensing_player(state: object, game_data: object, ctx: object = None,
                    objective: object = _UNSET) -> MagicMock:
    player = MagicMock()
    player.state = state
    player.game_data = game_data
    # `plan_once()` -> `plan_from_state()` sets `self._last_ctx` as a side
    # effect (`player.py:1087`); this mock stands in for that assignment
    # having already happened by the time `_sense` reads it.
    player._last_ctx = ctx if ctx is not None else NO_PROFILE_CONTEXT
    # `_initialize()` (called by `plan_once()`, BEFORE `plan_from_state()`)
    # sets `self._objective` unconditionally (`player.py:970`) -- this mock
    # stands in for that assignment too. `_UNSET` (not `None`) is the
    # default so a caller testing the "objective never got set" branch can
    # still pass `objective=None` explicitly and have it mean that, rather
    # than "use the default".
    if objective is _UNSET:
        objective = CharacterObjective.from_game_data(
            game_data if isinstance(game_data, GameData) else GameData())
    player._objective = objective
    return player


def test_sense_returns_the_players_state_game_data_last_ctx_and_objective() -> None:
    """`_sense` mirrors `objective_audit_report.py`'s construction sequence:
    Config -> ClientManager -> an in-memory LearningStore -> GamePlayer.plan_once().
    Config/ClientManager/GamePlayer are substituted so this never touches the
    real token file, API client or network.

    I2: `_sense` must also return `player._last_ctx` — the context
    `plan_from_state` actually built for this cycle — not the
    `NO_PROFILE_CONTEXT` stand-in the command used to price against. The
    marker context here differs from `NO_PROFILE_CONTEXT` in a field the
    stand-in hard-codes (`bank_accessible`), so returning the wrong object
    would be visible by identity AND by value.

    T2.1: `_sense` must ALSO return `player._objective` -- the SAME
    `CharacterObjective` `_initialize()` builds and `resolve_root` resolves
    against on every live cycle, not a second one this command constructs
    itself. Pinned the same way as `_last_ctx`: return-by-identity against a
    marker object this test controls."""
    state = make_state(level=5)
    game_data = GameData()
    marker_ctx = replace(NO_PROFILE_CONTEXT, bank_accessible=False)
    marker_objective = CharacterObjective.from_game_data(game_data)
    player = _sensing_player(state, game_data, marker_ctx, marker_objective)
    with (
        patch.object(cmd.Config, "from_token_file",
                     return_value=MagicMock(game_data_ttl_minutes=5)),
        patch.object(cmd, "ClientManager"),
        patch.object(cmd, "GamePlayer", return_value=player),
    ):
        result_state, result_game_data, result_ctx, result_objective = cmd._sense("C3P0")

    assert result_state is state
    assert result_game_data is game_data
    assert result_ctx is marker_ctx
    assert result_objective is marker_objective
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


def test_sense_raises_bad_parameter_when_objective_could_not_be_sensed() -> None:
    """A state and game_data that sensed fine but an objective that never got
    built (`player._objective` still `None`, its `__init__` default) must
    also fail loudly -- the same "use only API data or fail" rule as the
    state/game_data check, extended to the third thing this seam now reads
    off the player."""
    state = make_state(level=5)
    game_data = GameData()
    player = _sensing_player(state, game_data, objective=None)
    with (
        patch.object(cmd.Config, "from_token_file",
                     return_value=MagicMock(game_data_ttl_minutes=5)),
        patch.object(cmd, "ClientManager"),
        patch.object(cmd, "GamePlayer", return_value=player),
    ):
        with pytest.raises(typer.BadParameter, match="could not sense state"):
            cmd._sense("C3P0")

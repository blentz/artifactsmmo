"""O1: the open-rung census (spec §3.5).

The census asserts that every `ReachSkillLevel(S, C+1)` reachable across the
scenario set has an open, XP-positive rung, or is a NAMED wall. These tests
exist to stop it becoming decorative, which for a census means exactly three
things:

* it must actually sweep something — `test_the_sweep_sees_the_whole_grid` pins
  lower bounds on cells, distinct `(skill, level)` pairs, ROUTED cells and
  WALLED cells, so a sweep that quietly discovered nothing fails instead of
  passing;
* its verdict must be production's — `test_a_cell_is_open_iff_an_arm_offers_a_rung`
  cross-reads `LevelSkill.is_applicable` against the census's own catalogue
  decomposition on all 336 cells, so the two cannot drift;
* it must be able to FAIL — `test_the_gate_fires_when_a_routed_skill_loses_its_rung`
  closes one routed skill through the production seam and asserts the residual
  fires, and `test_the_unexplained_residual_can_fire` exhibits the hole the
  wall taxonomy deliberately leaves open.

`test_the_zero_stat_harness_would_measure_the_fixture` is the fourth guard and
the one that caught the census measuring itself: with
`ScenarioCharacter.derive_combat_stats` at its default the harness makes every
monster unwinnable, so 65 extra cells wall for a reason that is a property of
the fixture and not of the game.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.actions import level_skill as level_skill_module
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.world_state import SKILL_NAMES, WorldState
from artifactsmmo_cli.audit import open_rung_completeness as orc
from artifactsmmo_cli.audit.open_rung_completeness import (
    RESIDUALS,
    OpenRungGap,
    RungInventory,
)

# Floors, not exact counts: a new scenario must not have to touch this file,
# but a sweep that goes blind must. The committed set is 42 scenarios x 8
# skills = 336 cells over 92 distinct (skill, level) pairs.
#
# The cell floor is `orc.MIN_CELLS`, NOT a local copy: `gen_open_rung.py
# --check` enforces the same number, and two floors that could drift would
# leave the script's copy — the one CI actually runs, on a path `scripts/*`
# omits from coverage — silently weaker than the suite's.
_MIN_PAIRS = 60
_MIN_ROUTED = 10
_MIN_WALLED = 1


@pytest.fixture(scope="module")
def results(bundle_game_data: GameData) -> list[orc.RungResult]:
    return orc.run_census(bundle_game_data)


def _closed_cells(game_data: GameData, *, derive_combat_stats: bool | None) -> int:
    """Cells with no open rung, when the scenario states are built with the
    given `derive_combat_stats` setting. `None` means AS COMMITTED — 32 of the
    scenarios opt the flag on and the rest leave it at its False default,
    which is what a census built straight on `scenario_state` would measure.
    The census forces it True for every cell."""
    closed = 0
    for scenario in SCENARIOS.values():
        state = scenario_state(
            scenario if derive_combat_stats is None
            else dataclasses.replace(scenario,
                                     derive_combat_stats=derive_combat_stats),
            game_data)
        for skill in SKILL_NAMES:
            level = state.skills[skill]
            if not LevelSkill(skill=skill, target_level=level + 1
                              ).is_applicable(state, game_data):
                closed += 1
    return closed


# --- anti-blindness ---------------------------------------------------------

def test_the_sweep_sees_the_whole_grid(results: list[orc.RungResult]) -> None:
    """Four floors, because a census that swept nothing would otherwise report
    total success forever — this repo has shipped exactly that once.

    The ROUTED and WALLED floors are the two that matter most: the residual
    `o1_silent_stall` is the intersection of "closed" and "routed", so a run
    with zero routed cells or zero closed cells could never report it and the
    gate's clean verdict would be meaningless.
    """
    assert len(results) >= orc.MIN_CELLS, len(results)
    pairs = {(r.skill, r.level) for r in results}
    assert len(pairs) >= _MIN_PAIRS, sorted(pairs)
    assert {r.skill for r in results} == set(SKILL_NAMES)
    assert {r.scenario for r in results} == set(SCENARIOS)
    assert sum(1 for r in results if r.routed) >= _MIN_ROUTED
    assert sum(1 for r in results if r.gap.startswith("wall_")) >= _MIN_WALLED
    # Named pins, so the floors cannot be met by one skill or one scenario.
    assert ("weaponcrafting", 10) in pairs
    assert ("jewelrycrafting", 35) in pairs


def test_a_cell_is_open_iff_an_arm_offers_a_rung(
        results: list[orc.RungResult]) -> None:
    """The census's catalogue decomposition and production's verdict are the
    SAME answer, on every cell.

    ONLY THE `obtainable` HALF IS A REAL PARITY CHECK, and the docstring says
    so rather than implying more. `LevelSkill.is_applicable` is
    `best_gather_resource_drop(...) is not None or has_grind_target(...)`, and
    `RungInventory.gather_rung` is literally that same
    `best_gather_resource_drop` call — that disjunct cannot disagree by
    construction. The load-bearing half is `obtainable > 0` against
    `has_grind_target`: two independent walks over the recipe table
    (short-circuiting existence versus a counted list), which is where a drift
    would actually appear and where the matrix's evidence columns would start
    explaining a verdict they did not produce.
    """
    for r in results:
        arm = (r.inventory.gather_rung is not None
               or r.inventory.obtainable > 0)
        assert r.open_rung is arm, r


def test_the_zero_stat_harness_would_measure_the_fixture(
        bundle_game_data: GameData, results: list[orc.RungResult]) -> None:
    """`census_state` forces `derive_combat_stats=True`, and that is load-bearing.

    `ScenarioCharacter.derive_combat_stats` defaults False and its own
    docstring says that under the resulting zero-stat states "`is_winnable` is
    False against EVERY monster". Every recipe leaf that is a monster drop is
    then unreachable, so cells wall for a reason that belongs to the harness.

    Three counts, pinned exactly because `open_rung_completeness`'s module
    docstring quotes them: 71 closed with the flag off everywhere, 20 closed
    on the scenarios AS COMMITTED (32 of the 42 opt in), 6 with the census's
    forced-on states. The as-committed number is the one that matters — it is
    what this census would report if `census_state` were `scenario_state`.
    """
    all_off = _closed_cells(bundle_game_data, derive_combat_stats=False)
    as_committed = _closed_cells(bundle_game_data, derive_combat_stats=None)
    derived = _closed_cells(bundle_game_data, derive_combat_stats=True)
    assert (all_off, as_committed, derived) == (71, 20, 6), \
        "update the module docstring's 71/20/6 note"
    # The opt-in count is PINNED, not merely restated. Both docstrings quote it,
    # and it silently rotted from 11 to 20 as scenarios were added — caught only
    # by a coverage audit, months later. A quoted number with no assertion behind
    # it is the same defect class the reachability census now gates.
    opted_in = sum(1 for s in SCENARIOS.values() if s.derive_combat_stats)
    assert opted_in == 32, (
        "update the '32 of the 42 opt in' count in this docstring AND in "
        "open_rung_completeness's module docstring")
    assert sum(1 for r in results if not r.open_rung) == derived


# --- the residuals can fire -------------------------------------------------

def test_the_gate_fires_when_a_routed_skill_loses_its_rung(
        bundle_game_data: GameData, monkeypatch: pytest.MonkeyPatch) -> None:
    """Close `jewelrycrafting`'s craft arm at the production seam and the
    census must report `o1_silent_stall` — a root the graph routes to and the
    planner cannot serve.

    The seam is `level_skill.has_grind_target`, the name
    `LevelSkill.is_applicable` actually calls. Only jewelrycrafting is closed,
    so the other seven skills keep answering normally and the residual cannot
    come from a blanket outage. Jewelrycrafting is not a gathering skill, so
    the gather arm is already None and this one patch closes the cell.
    """
    real = level_skill_module.has_grind_target

    def closed_for_jewelry(skill: str, state: WorldState,
                           game_data: GameData) -> bool:
        if skill == "jewelrycrafting":
            return False
        return real(skill, state, game_data)

    monkeypatch.setattr(level_skill_module, "has_grind_target",
                        closed_for_jewelry)
    broken = orc.run_census(bundle_game_data)
    stalls = [r for r in broken
              if r.gap == OpenRungGap.O1_SILENT_STALL.value]
    assert stalls, "the census cannot report the obligation's own failure"
    assert {r.skill for r in stalls} == {"jewelrycrafting"}
    assert all(r.gap in RESIDUALS for r in stalls)
    assert OpenRungGap.O1_SILENT_STALL.value in orc.summary_line(broken)


def test_the_unexplained_residual_can_fire() -> None:
    """The hole the wall taxonomy leaves open on purpose.

    `best_gather_resource_drop` returns None when the highest in-range
    resource has no drop item, even though that resource is XP-positive. A
    cell in that shape has an XP-positive gather candidate (so it is not
    `wall_all_rungs_grey`) and XP-positive recipes (so `wall_rungs_unobtainable`
    is refused by its `not gather_xp_positive` conjunct) — and lands in the
    residual, which is exactly where an unnameable closure belongs.
    """
    inventory = RungInventory(
        in_level=4, xp_positive=4, obtainable=0, above=3,
        gather_in_level=2, gather_above=1, gather_xp_positive=True,
        gather_rung=None)
    assert orc.classify_gap(False, False, inventory) is OpenRungGap.O1_UNEXPLAINED


# --- classify_gap, arm by arm ----------------------------------------------

def _inventory(in_level: int = 0, xp_positive: int = 0, obtainable: int = 0,
               above: int = 0, gather_in_level: int = 0, gather_above: int = 0,
               gather_xp_positive: bool = False) -> RungInventory:
    """A closed-cell inventory, defaulting every counter to "nothing there".
    `gather_rung` is always None: a cell with a gather rung is OPEN by
    definition and `classify_gap` would never see it."""
    return RungInventory(
        in_level=in_level, xp_positive=xp_positive, obtainable=obtainable,
        above=above, gather_in_level=gather_in_level,
        gather_above=gather_above, gather_xp_positive=gather_xp_positive,
        gather_rung=None)


def test_an_open_cell_passes_whatever_the_evidence_says() -> None:
    assert orc.classify_gap(True, True, _inventory()) is OpenRungGap.OPEN_RUNG


def test_routing_is_tested_before_any_wall() -> None:
    """A closed cell the graph routes to is `o1_silent_stall` EVEN THOUGH the
    catalogue would happily explain it as `wall_rungs_unobtainable`.

    That ordering is the obligation: naming a wall the graph never consults
    would launder a live stall into an explanation. This inventory satisfies
    the unobtainable arm exactly, so if the arms were reordered the verdict
    would flip and this test would fail.
    """
    unobtainable = _inventory(in_level=9, xp_positive=9, above=4)
    assert orc.classify_gap(False, False, unobtainable) is \
        OpenRungGap.WALL_RUNGS_UNOBTAINABLE
    assert orc.classify_gap(False, True, unobtainable) is \
        OpenRungGap.O1_SILENT_STALL


def test_an_empty_skill_catalogue_is_a_residual_not_the_gentlest_wall() -> None:
    """A skill the catalogue offers NOTHING is `skill_catalogue_empty`, which
    fails the gate — not `wall_ladder_topped`, which does not.

    Both shapes satisfy "nothing above me", so only the arm ORDER separates
    them, and getting it backwards means a bundle that lost a skill's rows
    reports "an honest end" and `--check` exits 0. `census-gate.yml` runs the
    eight scripts and no pytest, so the suite's wall-count pin does not cover
    CI; this arm does.
    """
    empty = _inventory()
    assert orc.classify_gap(False, False, empty) is \
        OpenRungGap.SKILL_CATALOGUE_EMPTY
    assert OpenRungGap.SKILL_CATALOGUE_EMPTY.value in RESIDUALS
    assert OpenRungGap.WALL_LADDER_TOPPED.value not in RESIDUALS


def test_nothing_above_is_a_topped_ladder() -> None:
    """Not reached by the committed scenario set — no scenario declares a
    skill at the catalogue's top — so it is covered here. It is what a
    level-50 skill must classify as, and it must not be an `o1_unexplained`.

    `in_level=12` is load-bearing: it is what distinguishes a FINISHED ladder
    from an ABSENT one, and dropping it moves this cell to the residual above.
    """
    assert orc.classify_gap(False, False, _inventory(in_level=12, above=0)) is \
        OpenRungGap.WALL_LADDER_TOPPED


def test_nothing_in_reach_is_below_the_first_rung() -> None:
    """A skill with content above and none at or below the current level: the
    character stands under the bottom of its own ladder."""
    assert orc.classify_gap(False, False, _inventory(above=7, gather_above=2)) is \
        OpenRungGap.WALL_BELOW_FIRST_RUNG


def test_every_reachable_rung_grey_is_named() -> None:
    """Rungs are in reach, every one is in the server's zero-xp band — the
    `sunflower_field`-at-alchemy-17 shape."""
    grey = _inventory(in_level=6, xp_positive=0, above=3,
                      gather_in_level=1, gather_above=1)
    assert orc.classify_gap(False, False, grey) is OpenRungGap.WALL_ALL_RUNGS_GREY


# --- the live answer this census exists to give -----------------------------

def test_weaponcrafting_ten_has_an_open_rung(
        results: list[orc.RungResult]) -> None:
    """The epic's live characters sit at `weaponcrafting == 10` and cannot
    climb. This census says the RUNG is open at that level — 18 in-level
    weaponcrafting recipes, all XP-positive, several obtainable — so whatever
    stops them is downstream of O1, not a missing rung.

    Pinned so the claim in the task report stays checkable: if a future
    catalogue or obtainability change closes weaponcrafting 10, this fails and
    the O1 story for those characters changes.
    """
    cells = [r for r in results
             if r.skill == "weaponcrafting" and r.level == 10]
    assert cells, "no scenario sits at weaponcrafting 10 any more"
    for cell in cells:
        assert cell.gap == OpenRungGap.OPEN_RUNG.value, cell
        assert cell.inventory.obtainable > 0, cell


def test_the_only_walls_today_are_high_weaponcrafting(
        results: list[orc.RungResult]) -> None:
    """Today's whole residual-free wall set, pinned as a finding rather than a
    success: six cells, all `weaponcrafting` at 35, 40 or 42, each with
    XP-positive rungs in reach and NOT ONE with a reachable material set.

    A change that opens them is a fix and should update this test; a change
    that silently empties `results` of walls is the census going blind, which
    `test_the_sweep_sees_the_whole_grid`'s floor also catches.
    """
    walls = [r for r in results if not r.passed]
    assert len(walls) == 6
    for wall in walls:
        assert wall.skill == "weaponcrafting"
        assert wall.level in (35, 40, 42)
        assert wall.gap == OpenRungGap.WALL_RUNGS_UNOBTAINABLE.value
        assert wall.inventory.xp_positive > 0
        assert wall.inventory.obtainable == 0
        assert not wall.routed


# --- routing ----------------------------------------------------------------

def test_routing_counts_the_alternatives_not_only_the_root(
        bundle_game_data: GameData) -> None:
    """`RootResolution.alternatives` is where `strategy_driver` falls through
    when the root's step goal returns None, so an alternative is as routable
    as the head.

    `l30_rune_fill` resolves to an `ObtainItem` root and carries
    `ReachSkillLevel(jewelrycrafting, ...)` ONLY in its alternatives; dropping
    the alternatives from `routed_skills` would report it unrouted and hide
    any stall behind it.
    """
    state = orc.census_state(SCENARIOS["l30_rune_fill"], bundle_game_data)
    assert "jewelrycrafting" in orc.routed_skills(state, bundle_game_data)


# --- rendering --------------------------------------------------------------

def test_the_matrix_renders_every_cell_and_the_summary(
        results: list[orc.RungResult]) -> None:
    matrix = orc.render_matrix(results)
    rows = [line for line in matrix.splitlines() if line.startswith("| l")]
    assert len(rows) == len(results)
    assert orc.summary_line(results) in matrix
    assert "**wall_rungs_unobtainable**" in matrix
    assert "| l40_band_entry | weaponcrafting | 35 | 36 |" in matrix
    # Finding 4: every field `classify_gap` reads must be reconstructable from
    # the row, so the three gather columns are part of the header contract.
    assert "| g-in | g-above | g-xp+ | gather rung |" in matrix
    assert orc.routing_breakdown(results) in matrix


def test_the_summary_reports_both_residuals_and_the_pair_count(
        results: list[orc.RungResult]) -> None:
    line = orc.summary_line(results)
    assert f"{len(results)} cells over 92 distinct (skill, level) pairs" in line
    assert "o1_silent_stall 0" in line
    assert "o1_unexplained 0" in line
    assert "skill_catalogue_empty 0" in line
    assert "walled 6" in line


def test_the_routing_breakdown_scopes_the_residual(
        results: list[orc.RungResult]) -> None:
    """The residual arm reaches only the ROUTED subset, and the matrix says so.

    SEVEN of the eight skills are routed now, up from three: restoring the
    standalone skill root (`decisions/root._orphan_skill_roots`) put cooking,
    fishing, mining and woodcutting on the routed side, and the routed cell
    count moved 26 -> 194 of 336. Before it, `ReachSkillLevel` had exactly one
    producer — a GEAR target's crafting skill — so a skill nothing equips could
    not be routed by any scenario and its closures could only ever be explained
    walls. Alchemy is the one skill still unrouted, and correctly: its potions
    ARE utility equippables, so it is a prerequisite skill that a gear target
    can name whenever a utility slot wants one.

    The scope line still matters — 142 cells remain unrouted — but it now
    understates far less than it did.
    """
    line = orc.routing_breakdown(results)
    routed_skills = {r.skill for r in results if r.routed}
    assert routed_skills == {"jewelrycrafting", "gearcrafting", "weaponcrafting",
                             "cooking", "fishing", "mining", "woodcutting"}
    assert "alchemy" not in routed_skills
    assert f"{len(routed_skills)} of {len(SKILL_NAMES)} skills" in line
    assert f"{sum(1 for r in results if r.routed)} of {len(results)} cells" in line
    # Ordered by cell count, so the reader sees the widest arm first.
    assert line.index("cooking") < line.index("jewelrycrafting")
    assert line.index("jewelrycrafting") < line.index("weaponcrafting")


def test_the_committed_matrix_is_the_current_answer(
        results: list[orc.RungResult]) -> None:
    """`gen_open_rung.py --check` REWRITES the matrix and `formal/gate.sh` does
    not restore it (unlike the craft and liveness matrices, whose content is
    environment-dependent by design — this census reads only the committed
    bundle). So a committed doc that disagrees with a fresh run leaves the tree
    dirty on every gate pass, one `git commit -a` away from being committed as
    noise. Asserting the equality here means the suite, not the gate, is what
    tells you to regenerate — and it subsumes a bare determinism check, because
    a run whose row order varied would flap against a fixed file.
    """
    committed = Path("docs/behavioral_completeness/OPEN_RUNG_MATRIX.md")
    assert committed.read_text() == orc.render_matrix(results), \
        "regenerate with `uv run python scripts/gen_open_rung.py`"

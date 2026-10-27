"""O1: the skill-climb census (wave-3 resolution design §3.5; restored by
ruling AK of the global gear objective, which had deleted it as a "rung"
census — its cell is a SKILL level `C+1`, not a character tier).

The census asserts that every `ReachSkillLevel(S, C+1)` the root walk routes
to across the scenario set can plan, or is a NAMED wall. These tests stop it
becoming decorative:

* it must sweep something — `test_the_sweep_sees_the_whole_grid` pins floors on
  cells, distinct `(skill, level)` pairs, ROUTED cells and WALLED cells;
* its verdict must be production's — `test_a_cell_is_open_iff_an_arm_offers_a_climb`
  cross-reads `skill_is_grindable` against the census's own decomposition;
* it must be able to FAIL — `test_the_gate_fires_when_a_routed_skill_loses_its_climb`
  closes one routed skill at the production seam and asserts the residual
  fires, and `test_the_unexplained_residual_can_fire` exhibits the hole the
  wall taxonomy deliberately leaves open;
* its routing must be the gear objective's walk — `test_routing_reads_the_gear_objective`.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from artifactsmmo_cli.ai import skill_grindable as skill_grindable_module
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.scenario import SCENARIOS, derived_scenario_state
from artifactsmmo_cli.ai.world_state import SKILL_NAMES, WorldState
from artifactsmmo_cli.audit import skill_climb_completeness as scc
from artifactsmmo_cli.audit.skill_climb_completeness import (
    RESIDUALS,
    ClimbGap,
    ClimbInventory,
)
from tests.test_ai.shared_world import attached, shared_world

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")

pytestmark = pytest.mark.xdist_group("skill_climb_census")
"""Ruling AD: the whole module on ONE xdist worker (`--dist loadgroup`), so its
module-scoped census sweep runs once rather than once per worker."""

# Floors, not exact counts, for the anti-blindness pin: a new scenario must not
# have to touch them, but a sweep that goes blind must. The cell floor is
# `scc.MIN_CELLS`, the number `gen_skill_climb.py --check` also enforces.
_MIN_PAIRS = 60
_MIN_ROUTED = 10
_MIN_WALLED = 1

WALLS = 10
"""Today's closed cells (all `wall_unobtainable`). 9 -> 10 with ruling T14a-E
(a fight's monster is a route only where the walk reaches): `l47_depth3_amulet`'s
weaponcrafting 40 rungs (the mithril tools and gloves) all need
`cultist_alchemist`'s drops from `interior:-1,13`, whose door asks a held
`cultist_cloak` the sheet does not have."""
GEAR_WALLS = 4
"""Of those, gearcrafting 42 in the four l48 scenarios."""
ROUTED_SKILLS = frozenset({"gearcrafting", "jewelrycrafting", "weaponcrafting", "mining"})
"""The skills the gear objective's walk routes to on the committed scenarios:
the three crafting skills that gate `L*` pieces, and mining in one scenario
(`l12_taskgated_bag`)."""
ROUTED_SCENARIO = "l10_weapon_upgrade"
ROUTED_SKILL = "gearcrafting"
"""`l10_weapon_upgrade`'s objective offers `ReachSkillLevel(gearcrafting, 2)`
for a skill-gated `L*` piece, as an alternative behind the iron_sword."""


@pytest.fixture(scope="module", autouse=True)
def _shared_worlds() -> Iterator[None]:
    """Ruling AD: the census runs on the process-wide bundle world with the
    gear objective memoized per (state, world) — harness only; the script
    attaches its own objective once per scenario. Patched on the census module
    itself, so `run_census` and the tests read the same objects."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(scc, "attach_gear_objective", attached)
        yield


@pytest.fixture(scope="module")
def world() -> GameData:
    return shared_world(BUNDLE)


@pytest.fixture(scope="module")
def results(world: GameData) -> list[scc.ClimbResult]:
    return scc.run_census(world)


# --- anti-blindness ---------------------------------------------------------

def test_the_sweep_sees_the_whole_grid(results: list[scc.ClimbResult]) -> None:
    """Four floors: `silent_stall` is "closed AND routed", so a run with zero
    routed or zero closed cells could never report it."""
    assert len(results) >= scc.MIN_CELLS, len(results)
    pairs = {(r.skill, r.level) for r in results}
    assert len(pairs) >= _MIN_PAIRS, sorted(pairs)
    assert {r.skill for r in results} == set(SKILL_NAMES)
    assert {r.scenario for r in results} == set(SCENARIOS)
    assert sum(1 for r in results if r.routed) >= _MIN_ROUTED
    assert sum(1 for r in results if r.gap.startswith("wall_")) >= _MIN_WALLED
    assert ("weaponcrafting", 10) in pairs
    assert ("jewelrycrafting", 35) in pairs


def test_a_cell_is_open_iff_an_arm_offers_a_climb(
        results: list[scc.ClimbResult]) -> None:
    """The census's decomposition and production's verdict agree on every
    cell. Only the `obtainable` half is a real parity check: `gather_drop` IS
    the `best_gather_resource_drop` call `skill_is_grindable` makes."""
    for r in results:
        arm = r.inventory.gather_drop is not None or r.inventory.obtainable > 0
        assert r.open_climb is arm, r


# --- the residuals can fire -------------------------------------------------

def test_the_gate_fires_when_a_routed_skill_loses_its_climb(
        world: GameData, monkeypatch: pytest.MonkeyPatch) -> None:
    """Close `gearcrafting`'s craft arm at the production seam
    (`skill_grindable.has_grind_target`) and the census must report
    `silent_stall`: a root the walk routes to and the planner cannot serve.
    Only gearcrafting is closed, and it gathers nothing, so the residual cannot
    come from a blanket outage."""
    real = skill_grindable_module.has_grind_target

    def closed_for_gear(skill: str, state: WorldState, game_data: GameData) -> bool:
        if skill == "gearcrafting":
            return False
        return real(skill, state, game_data)

    monkeypatch.setattr(skill_grindable_module, "has_grind_target", closed_for_gear)
    broken = scc.run_census(world)
    stalls = [r for r in broken if r.gap == ClimbGap.SILENT_STALL.value]
    assert stalls, "the census cannot report the obligation's own failure"
    assert {r.skill for r in stalls} == {"gearcrafting"}
    assert all(r.gap in RESIDUALS for r in stalls)
    assert "silent_stall 0" not in scc.summary_line(broken)


def test_the_unexplained_residual_can_fire() -> None:
    """`best_gather_resource_drop` returns None when the highest in-range
    resource has no drop item, though it is XP-positive: not all-grey, not
    unobtainable (the `not gather_xp_positive` conjunct), so it lands in the
    residual, which is where an unnameable closure belongs."""
    inventory = ClimbInventory(
        in_level=4, xp_positive=4, obtainable=0, above=3,
        gather_in_level=2, gather_above=1, gather_xp_positive=True,
        gather_drop=None)
    assert scc.classify_gap(False, False, inventory) is ClimbGap.UNEXPLAINED


# --- classify_gap, arm by arm ----------------------------------------------

def _inventory(in_level: int = 0, xp_positive: int = 0, obtainable: int = 0,
               above: int = 0, gather_in_level: int = 0, gather_above: int = 0,
               gather_xp_positive: bool = False) -> ClimbInventory:
    """A closed-cell inventory, every counter defaulting to "nothing there"."""
    return ClimbInventory(
        in_level=in_level, xp_positive=xp_positive, obtainable=obtainable,
        above=above, gather_in_level=gather_in_level,
        gather_above=gather_above, gather_xp_positive=gather_xp_positive,
        gather_drop=None)


def test_an_open_cell_passes_whatever_the_evidence_says() -> None:
    assert scc.classify_gap(True, True, _inventory()) is ClimbGap.OPEN


def test_routing_is_tested_before_any_wall() -> None:
    """A closed routed cell is `silent_stall` even though the catalogue would
    explain it as `wall_unobtainable`; reordering the arms flips this."""
    unobtainable = _inventory(in_level=9, xp_positive=9, above=4)
    assert scc.classify_gap(False, False, unobtainable) is ClimbGap.WALL_UNOBTAINABLE
    assert scc.classify_gap(False, True, unobtainable) is ClimbGap.SILENT_STALL


def test_an_empty_skill_catalogue_is_a_residual_not_the_gentlest_wall() -> None:
    assert scc.classify_gap(False, False, _inventory()) is ClimbGap.SKILL_CATALOGUE_EMPTY
    assert ClimbGap.SKILL_CATALOGUE_EMPTY.value in RESIDUALS
    assert ClimbGap.WALL_SKILL_TOPPED.value not in RESIDUALS


def test_nothing_above_is_a_topped_skill() -> None:
    """What a level-50 skill must classify as; `in_level=12` separates a
    finished skill from an absent one."""
    assert scc.classify_gap(False, False, _inventory(in_level=12)) is \
        ClimbGap.WALL_SKILL_TOPPED


def test_nothing_in_reach_is_below_the_first_recipe() -> None:
    assert scc.classify_gap(False, False, _inventory(above=7, gather_above=2)) is \
        ClimbGap.WALL_BELOW_FIRST_RECIPE


def test_every_reachable_recipe_grey_is_named() -> None:
    grey = _inventory(in_level=6, above=3, gather_in_level=1, gather_above=1)
    assert scc.classify_gap(False, False, grey) is ClimbGap.WALL_ALL_GREY


# --- the live answer this census exists to give -----------------------------

def test_weaponcrafting_ten_has_an_open_climb(results: list[scc.ClimbResult]) -> None:
    """Characters at `weaponcrafting == 10` have an open climb: several
    obtainable XP-positive recipes."""
    cells = [r for r in results if r.skill == "weaponcrafting" and r.level == 10]
    assert cells, "no scenario sits at weaponcrafting 10 any more"
    for cell in cells:
        assert cell.gap == ClimbGap.OPEN.value, cell
        assert cell.inventory.obtainable > 0, cell


def test_the_walls_today_are_high_weapon_and_gearcrafting(
        results: list[scc.ClimbResult]) -> None:
    """Today's whole wall set, pinned as a FINDING: `weaponcrafting` at 35 or
    40 or 42 and `gearcrafting` at 42 (weaponcrafting 40 opened 2026-10-10, when
    the drop gate began wearing a potion loadout, and closed again on
    `l47_depth3_amulet` with ruling T14a-E: its drops lie behind a door the
    sheet holds no key for; see `WALLS`) (the l48 scenarios, whose one recipe needs a
    `diamond_stone` from the tile-less `strange_rocks`), each with XP-positive
    recipes in reach and NOT ONE with a reachable material set, and none
    routed. A change that opens one is a fix and updates this test."""
    walls = [r for r in results if not r.passed]
    assert len(walls) == WALLS
    assert sum(wall.skill == "gearcrafting" for wall in walls) == GEAR_WALLS
    for wall in walls:
        assert (wall.skill, wall.level) in {("weaponcrafting", 35), ("weaponcrafting", 40),
                                            ("weaponcrafting", 42), ("gearcrafting", 42)}
        assert wall.gap == ClimbGap.WALL_UNOBTAINABLE.value
        assert wall.inventory.xp_positive > 0
        assert wall.inventory.obtainable == 0
        assert not wall.routed


# --- routing ----------------------------------------------------------------

def test_routing_reads_the_gear_objective(world: GameData) -> None:
    """The routed set is the gear objective's walk: a skill-gated missing `L*`
    piece puts its crafting skill's next level on offer. Without the objective
    on the context the walk is the wall and routes nothing."""
    state = derived_scenario_state(SCENARIOS[ROUTED_SCENARIO], world)
    assert ROUTED_SKILL in scc.routed_skills(state, world)


# --- rendering --------------------------------------------------------------

def test_the_matrix_renders_every_cell_and_the_summary(
        results: list[scc.ClimbResult]) -> None:
    matrix = scc.render_matrix(results)
    rows = [line for line in matrix.splitlines() if line.startswith("| l")]
    assert len(rows) == len(results)
    assert scc.summary_line(results) in matrix
    assert scc.routing_breakdown(results) in matrix
    assert "**wall_unobtainable**" in matrix
    assert "| g-in | g-above | g-xp+ | gather drop |" in matrix


def test_the_summary_reports_every_residual_and_the_pair_count(
        results: list[scc.ClimbResult]) -> None:
    line = scc.summary_line(results)
    pairs = len({(r.skill, r.level) for r in results})
    assert f"{len(results)} cells over {pairs} distinct (skill, level) pairs" in line
    assert "silent_stall 0" in line
    assert "unexplained 0" in line
    assert "skill_catalogue_empty 0" in line
    assert f"walled {WALLS}" in line


def test_the_routing_breakdown_scopes_the_residual(
        results: list[scc.ClimbResult]) -> None:
    """The residual reaches only the ROUTED subset, and the matrix says so,
    widest skill first."""
    line = scc.routing_breakdown(results)
    routed = {r.skill for r in results if r.routed}
    assert routed == ROUTED_SKILLS
    assert f"{len(routed)} of {len(SKILL_NAMES)} skills" in line
    assert f"{sum(1 for r in results if r.routed)} of {len(results)} cells" in line


def test_the_committed_matrix_is_the_current_answer(
        results: list[scc.ClimbResult]) -> None:
    """`gen_skill_climb.py --check` REWRITES the matrix and `formal/gate.sh`
    does not restore it (it reads only the committed bundle), so a committed
    doc that disagrees with a fresh run leaves the tree dirty on every gate
    pass. The suite, not the gate, says regenerate — and this subsumes a
    determinism check."""
    committed = Path("docs/behavioral_completeness/SKILL_CLIMB_MATRIX.md")
    assert committed.read_text() == scc.render_matrix(results), \
        "regenerate with `uv run python scripts/gen_skill_climb.py`"

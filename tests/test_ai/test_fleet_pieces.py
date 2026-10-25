"""The board pieces a crafter's role serves (spec 2026-10-18 §2.5, "the
crafter's own objective"), read off the real bundle catalogue."""

from fractions import Fraction
from pathlib import Path

from artifactsmmo_cli.ai.fleet_piece import FleetPiece
from artifactsmmo_cli.ai.fleet_pieces import fleet_pieces
from tests.test_ai.fixtures import make_state
from tests.test_ai.shared_world import shared_world

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"

BOARD = {
    "iron_shield": (1, Fraction(3)),    # gearcrafting 10
    "iron_sword": (2, Fraction(5)),     # weaponcrafting 10
    "copper_helmet": (1, Fraction(1)),  # gearcrafting 1
    "feather": (4, Fraction(0)),        # no producing skill
}


def test_a_logger_serves_the_gearcrafting_pieces_in_board_order() -> None:
    gd = shared_world(BUNDLE)
    assert fleet_pieces(make_state(), gd, "logger", BOARD, {}) == (
        FleetPiece("iron_shield", "gearcrafting", 10, Fraction(3)),
        FleetPiece("copper_helmet", "gearcrafting", 1, Fraction(1)))


def test_no_role_serves_no_fleet_piece() -> None:
    assert fleet_pieces(make_state(), shared_world(BUNDLE), None, BOARD, {}) == ()


def test_a_held_copy_is_no_fleet_piece() -> None:
    """A copy in the bag or the bank is supplied by a deposit, not a climb."""
    gd = shared_world(BUNDLE)
    state = make_state(inventory={"iron_shield": 1}, bank_items={"copper_helmet": 1})
    assert fleet_pieces(state, gd, "logger", BOARD, {}) == ()


def test_a_skill_another_character_climbs_makes_no_fleet_piece() -> None:
    """Ruling T7a/T7c: a second logger serves the role's gather demand, but the
    fleet assigned gearcrafting to Ana, so this character climbs for none of
    the board's gearcrafting pieces; its own assignment makes them its own."""
    gd = shared_world(BUNDLE)
    me = make_state(character="Bea")
    assert fleet_pieces(me, gd, "logger", BOARD, {"gearcrafting": "Ana"}) == ()
    assert len(fleet_pieces(me, gd, "logger", BOARD, {"gearcrafting": "Bea"})) == 2

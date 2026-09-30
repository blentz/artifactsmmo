"""The joint-walk census (Phase 2d-L1): each class is reachable, and the
catalogue run completes."""

import json
from pathlib import Path
from unittest.mock import patch

from artifactsmmo_cli.ai.decompose_core import Route, can_obtain
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit import joint_walk_census
from artifactsmmo_cli.audit.joint_walk_census import (
    JointCell,
    JointGap,
    classify,
    exact_can,
    independent_can,
    render_matrix,
    run_cell,
    summary_line,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")
UNBOUNDED = 10**9

# X needs 2 A + 1 B; B needs 2 A; A has no route.
SHARED = {"X": (Route("x", 1, UNBOUNDED, (("A", 2), ("B", 1))),),
          "B": (Route("b", 1, UNBOUNDED, (("A", 2),)),)}
# root needs X + Y; X: (M + Z) or free; Y needs M.
GREEDY = {"root": (Route("r", 1, UNBOUNDED, (("X", 1), ("Y", 1))),),
          "X": (Route("x1", 1, UNBOUNDED, (("M", 1), ("Z", 1))), Route("x2", 1, UNBOUNDED, ())),
          "Y": (Route("y", 1, UNBOUNDED, (("M", 1),)),)}


def test_a_shared_material_the_old_walk_counted_twice() -> None:
    bag = {"A": 2}
    assert independent_can("X", 1, bag, SHARED)
    assert not exact_can("X", 1, bag, SHARED)
    assert not can_obtain("X", 1, bag, SHARED)
    assert classify(True, False, False) is JointGap.SHARED_SHORTAGE


def test_a_greedy_false_negative() -> None:
    bag = {"M": 1, "Z": 1}
    assert exact_can("root", 1, bag, GREEDY)
    assert not can_obtain("root", 1, bag, GREEDY)
    assert classify(True, False, True) is JointGap.GREEDY_FALSE_NEGATIVE


def test_agreement_and_the_path_guard() -> None:
    looped = {"A": (Route("a", 1, UNBOUNDED, (("A", 1),)),)}
    assert not independent_can("A", 1, {}, looped)
    assert not exact_can("A", 1, {}, looped)
    assert independent_can("A", 1, {"A": 1}, looped)
    capped = {"A": (Route("a", 1, 0, ()), Route("b", 1, UNBOUNDED, ()))}
    assert independent_can("A", 2, {}, capped) and exact_can("A", 2, {}, capped)
    first_covers = {"A": (Route("a", 1, UNBOUNDED, ()), Route("b", 1, UNBOUNDED, ()))}
    assert independent_can("A", 3, {}, first_covers)
    assert classify(True, True, True) is JointGap.AGREE
    assert classify(False, False, False) is JointGap.AGREE


def test_a_search_past_its_bound_gives_no_verdict() -> None:
    with patch.object(joint_walk_census, "EXACT_STATE_BOUND", 0):
        assert run_cell("copper_bar", "one_run_each", _gd()).gap is JointGap.SEARCH_CAPPED
    assert classify(True, True, None) is JointGap.SEARCH_CAPPED


def test_the_catalogue_cells_render() -> None:
    gd = _gd()
    cells = [run_cell("copper_bar", holding, gd) for holding in joint_walk_census.HOLDINGS]
    assert all(c.gap is JointGap.AGREE for c in cells)
    odd = JointCell("x", "empty", True, False, False, JointGap.SHARED_SHORTAGE)
    doc = render_matrix([*cells, odd])
    assert "| x | empty | True | False | False | shared_shortage |" in doc
    assert summary_line([*cells, odd]).startswith("3 cells; agree 2, shared_shortage 1")


def test_run_census_covers_every_recipe_in_both_holdings() -> None:
    gd = _gd()
    with patch.object(joint_walk_census, "craftable_recipes", return_value=["copper_bar"]):
        cells = joint_walk_census.run_census(gd)
    assert [(c.recipe, c.holding) for c in cells] == [("copper_bar", "empty"), ("copper_bar", "one_run_each")]


def _gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))

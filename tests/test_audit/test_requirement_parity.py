"""Thin tests for the requirement-walk parity census (Wave 0).

The census is CHARACTERIZATION-first: it pins what the six requirement walks
answer TODAY, defects included. These tests therefore assert that the defects
are still OBSERVABLE. A characterization that silently stops observing is worse
than no characterization, because later waves would read its silence as
agreement.

If a count here goes to zero, exactly one of two things is true:
  * the corresponding D-defect was FIXED — update the test and cite the D-number;
  * the census stopped watching — which is the bug this file exists to catch.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit import requirement_parity as rp


@pytest.fixture(scope="module")
def rows(bundle_game_data: GameData) -> list[rp.WalkRow]:
    return rp.run_census(bundle_game_data)


# --- shape -----------------------------------------------------------------

def test_census_covers_every_craftable(bundle_game_data: GameData,
                                       rows: list[rp.WalkRow]) -> None:
    from artifactsmmo_cli.audit.craft_census import craftable_recipes
    assert [r.code for r in rows] == craftable_recipes(bundle_game_data)
    assert len(rows) > 300, "corpus collapsed — the census would pin nothing"


def test_order_is_deterministic(bundle_game_data: GameData) -> None:
    """Re-running must give byte-identical answers, or the drift gate would
    flap and every wave signal would be noise."""
    assert rp.render_matrix(rp.run_census(bundle_game_data)) == \
        rp.render_matrix(rp.run_census(bundle_game_data))


# --- the four drift defects, pinned as OBSERVABLE ---------------------------

def test_d1_namespace_split_is_observable(rows: list[rp.WalkRow]) -> None:
    """D1: `recipe_closure` speaks RESOURCE codes, everyone else speaks ITEMS.

    Concretely, `copper_dagger` reports `copper_rocks` in its closure resources
    while its demand map says `copper_ore` — the same physical thing under two
    namespaces. Wave 3+ collapses this.
    """
    assert rp.d1_namespace_split(rows) > 0


def test_d2_drop_blindness_is_observable(rows: list[rp.WalkRow]) -> None:
    """D2: the two-set return cannot represent a monster-drop leaf, so a demand
    item exists that `recipe_closure` reports in NEITHER set."""
    assert rp.d2_drop_blind(rows) > 0


def test_d3_skill_shape_disagreement_is_observable(rows: list[rp.WalkRow]) -> None:
    """D3: `objective_needs` yields skill NAMES; `_item_skill_gap` yields one
    worst `(skill, current, required)`. Rows exist where one is empty and the
    other is not."""
    assert rp.d3_skill_shape_disagreement(rows) > 0


def test_d1_and_d2_measure_different_things(rows: list[rp.WalkRow]) -> None:
    """Guards against the two counts silently collapsing into one metric — they
    overlap heavily but each has rows the other misses, and a refactor that
    made them identical would halve the census's resolution without failing
    any count-is-positive assertion."""
    d1 = {r.code for r in rows
          if r.closure_resources and not set(r.closure_resources) & set(r.demand_items)}
    d2 = {r.code for r in rows if r.drop_blind_items}
    assert d1 - d2, "D1 has no rows of its own"
    assert d2 - d1, "D2 has no rows of its own"


# --- the two LEGITIMATE axis differences ------------------------------------

def test_axis1_prerequisites_stays_one_ply(bundle_game_data: GameData,
                                           rows: list[rp.WalkRow]) -> None:
    """AXIS 1 is legitimate and must SURVIVE unification. `prerequisites` never
    returns more children than the recipe has direct ingredients; a wave that
    turned it into a closure would fail here."""
    assert rp.axis1_one_ply(rows, bundle_game_data)


def test_axis2_truncation_is_observable(rows: list[rp.WalkRow]) -> None:
    """AXIS 2 is legitimate too: `prerequisites` leafs on a ready non-craft
    source where `recipe_closure` descends regardless."""
    assert rp.axis2_truncates(rows) > 0


# --- falsifiability ---------------------------------------------------------

def test_census_goes_blind_if_a_walk_is_stubbed(bundle_game_data: GameData,
                                                monkeypatch) -> None:
    """The witness: prove the census CAN fail.

    Stubbing `recipe_closure` to return nothing must drive D1 and D2 to zero —
    i.e. the positive assertions above are measuring real walk output, not a
    constant. Without this they would pass against a census that had quietly
    stopped calling anything.
    """
    monkeypatch.setattr(rp, "recipe_closure", lambda gd, roots: (set(), set()))
    blinded = rp.run_census(bundle_game_data)
    assert rp.d1_namespace_split(blinded) == 0
    assert rp.d2_drop_blind(blinded) > 0  # everything is now unrepresentable


def test_axis1_check_can_fail(bundle_game_data: GameData,
                              rows: list[rp.WalkRow]) -> None:
    """Second witness: `axis1_one_ply` is a real comparison, not `return True`.

    Feed it a row claiming MORE prerequisite children than its recipe has
    ingredients — exactly the shape a wave would produce if it turned the
    one-ply walk into a closure — and the check must reject it. Without this,
    `test_axis1_prerequisites_stays_one_ply` would pass against a stub and the
    epic could flatten axis 1 unnoticed.
    """
    real = rows[0]
    ingredients = bundle_game_data.crafting_recipe(real.code) or {}
    inflated = replace(
        real,
        prereq_reprs=tuple(f"fake_child_{n}" for n in range(len(ingredients) + 1)),
    )
    assert not rp.axis1_one_ply([inflated], bundle_game_data)


def test_summary_line_reports_every_characterization(rows: list[rp.WalkRow]) -> None:
    line = rp.summary_line(rows)
    for token in ("targets", "D1", "D2", "D3", "axis2"):
        assert token in line

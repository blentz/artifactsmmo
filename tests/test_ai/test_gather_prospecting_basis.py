"""Every gather pricer reads one prospecting basis: the gather loadout's
(`attempt_prospecting.gather_prospecting`, Task 14f, ruling T14d-7c). A
gather's resource skill is mandatory: API data or fail."""

from datetime import UTC, datetime
from fractions import Fraction

import pytest

from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import Policy
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.source_kind import SourceKind
from tests.test_ai.fixtures import make_state

K = LearnedDrops((), (), Fraction(1, 100))
"""A drop-chance slope of 1/100 per prospecting point: a +100 tool doubles a
1-in-2 chance."""
NOW = datetime(2026, 10, 30, tzinfo=UTC)
EVERY_GATHER = Policy(all_gather_routes=True, gather_skill_gate=True, craft_skill_gate=True,
                      event_vendors=True, spawn_known=True, allow_grey=False,
                      vendor_routes=True, ge_routes=True, task_rewards=True, fight_gold=True,
                      drop_routes=True, price_climbs=False)


def _gd() -> GameData:
    """`pearl` drops 1 in 2 off `near_spot` and surely off `far_spot`; the
    fishing tool carries +100 prospecting."""
    gd = GameData()
    gd._item_stats = {
        "net": ItemStats(code="net", level=1, type_="weapon",
                         skill_effects={"fishing": -10}, prospecting=100),
        "pearl": ItemStats(code="pearl", level=1, type_="resource"),
    }
    gd.recipes_catalog.resource_drops_full = {
        "near_spot": [("pearl", 2, 1, 1)], "far_spot": [("pearl", 1, 1, 1)]}
    gd._resource_drops = {"near_spot": "pearl", "far_spot": "pearl"}
    gd._resource_skill = {"near_spot": ("fishing", 1), "far_spot": ("fishing", 1)}
    gd._resource_locations = {"near_spot": [(1, 0)], "far_spot": [(9, 0)]}
    return gd


def _gather(resource: str, tile: tuple[int, int]) -> GatherAction:
    return GatherAction(resource_code=resource, locations=frozenset({tile}),
                        drop_item_override="pearl", learned_drops=K)


def test_a_planned_gather_reads_the_gather_loadouts_prospecting() -> None:
    """The net is in the bag, not worn. The gather is made wearing it (the
    re-arm), so the 1-in-2 pearl is one gather a unit, not two."""
    gd = _gd()
    bare = make_state(skills={**make_state().skills, "fishing": 5})
    armed = make_state(skills={**make_state().skills, "fishing": 5}, inventory={"net": 1})
    assert _gather("near_spot", (1, 0)).gathers(bare, gd) == 2
    assert _gather("near_spot", (1, 0)).gathers(armed, gd) == 1


def test_the_narrowing_ranks_sources_at_the_gather_loadouts_prospecting() -> None:
    """At the worn total `far_spot` (a sure drop) beats `near_spot`; with the
    net the gather is made in both are sure, and the nearer one is kept."""
    gd = _gd()
    goal = GatherMaterialsGoal(target_item="pearl", needed={"pearl": 1})
    actions = [_gather("near_spot", (1, 0)), _gather("far_spot", (9, 0))]
    bare = make_state(skills={**make_state().skills, "fishing": 5})
    kept = goal.relevant_actions(actions, bare, gd)
    assert [a.resource_code for a in kept if isinstance(a, GatherAction)] == ["far_spot"]
    armed = make_state(skills={**make_state().skills, "fishing": 5}, inventory={"net": 1})
    kept = goal.relevant_actions(actions, armed, gd)
    assert [a.resource_code for a in kept if isinstance(a, GatherAction)] == ["near_spot"]


def test_a_resource_with_no_skill_raises_on_every_gather_read() -> None:
    gd = _gd()
    gd._resource_skill = {}
    state = make_state()
    action = _gather("near_spot", (1, 0))
    for read in (action.is_applicable, action.gathers, action.cost):
        with pytest.raises(ValueError, match="no gathering skill"):
            read(state, gd)


def _model(state) -> ObtainModel:
    ctx = SelectionContext(bank_accessible=True, bank_required_level=0,
                           bank_unlock_monster=None, initial_xp=0,
                           task_exchange_min_coins=0, combat_monster=None, learned_drops=K)
    return ObtainModel(state, _gd(), ctx, NOW)


def test_the_obtain_models_gather_order_reads_the_gather_loadouts_prospecting() -> None:
    """`ObtainModel._gather` puts the fewest expected gathers first, and
    `ready` ranks its gathers by the same figure: `far_spot` (a sure drop) at
    the worn total; with the net both are sure and the nearer `near_spot`
    leads (`_gather` keeps table order on the tie)."""
    bare = make_state(skills={**make_state().skills, "fishing": 5})
    armed = make_state(skills={**make_state().skills, "fishing": 5}, inventory={"net": 1})
    gathers = [r.via for r in _model(bare).routes("pearl") if r.kind is SourceKind.GATHER]
    assert gathers == ["far_spot", "near_spot"]
    gathers = [r.via for r in _model(armed).routes("pearl") if r.kind is SourceKind.GATHER]
    assert gathers == ["near_spot", "far_spot"]
    ready = [r.via for r in _model(bare).ready("pearl", EVERY_GATHER) if r.kind is SourceKind.GATHER]
    armed_ready = [r.via for r in _model(armed).ready("pearl", EVERY_GATHER)
                   if r.kind is SourceKind.GATHER]
    assert (ready, armed_ready) == (["far_spot", "near_spot"], ["near_spot", "far_spot"])


def test_the_walk_graph_ranks_gathers_at_the_gather_loadouts_prospecting() -> None:
    """`ObtainModel._ranked_gathers` (the walk graph's gather order): fewest
    expected gathers first, then the nearer tile. With the net both spots are
    sure and the nearer `near_spot` leads; at the worn total `far_spot` would."""
    armed = make_state(skills={**make_state().skills, "fishing": 5}, inventory={"net": 1})
    graph = _model(armed).walk_graph("pearl", EVERY_GATHER)
    assert [r.via for r in graph.sources["pearl"] if r.kind is SourceKind.GATHER] == [
        "near_spot", "far_spot"]

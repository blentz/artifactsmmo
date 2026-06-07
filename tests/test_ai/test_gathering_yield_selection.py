"""GatherMaterials.relevant_actions narrows a multi-source needed item to the
yield-optimal resource; single-source items are untouched; unknown table fail-open."""
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from tests.test_ai.fixtures import make_state


def _gd_two_sources():
    gd = GameData()
    # copper_ore is the PRIMARY drop of both rich_rocks (rate 1) and poor_rocks (rate 3).
    gd._resource_drops = {"rich_rocks": "copper_ore", "poor_rocks": "copper_ore"}
    gd._resource_drops_full = {
        "rich_rocks": [("copper_ore", 1, 1, 1)],
        "poor_rocks": [("copper_ore", 3, 1, 1)],
    }
    gd._resource_skill = {"rich_rocks": ("mining", 1), "poor_rocks": ("mining", 1)}
    return gd


def test_narrows_to_yield_optimal_source():
    gd = _gd_two_sources()
    state = make_state(skills={"mining": 5})
    goal = GatherMaterialsGoal(target_item="copper_ore", needed={"copper_ore": 10})
    actions = [
        GatherAction(resource_code="rich_rocks", locations=frozenset([(1, 0)])),
        GatherAction(resource_code="poor_rocks", locations=frozenset([(1, 0)])),
    ]
    relevant = goal.relevant_actions(actions, state, gd)
    codes = {a.resource_code for a in relevant if isinstance(a, GatherAction)}
    assert codes == {"rich_rocks"}, f"yield-optimal source only, got {codes}"


def test_single_source_untouched():
    gd = _gd_two_sources()
    state = make_state(skills={"mining": 5})
    goal = GatherMaterialsGoal(target_item="copper_ore", needed={"copper_ore": 10})
    actions = [GatherAction(resource_code="rich_rocks", locations=frozenset([(1, 0)]))]
    relevant = goal.relevant_actions(actions, state, gd)
    assert any(getattr(a, "resource_code", None) == "rich_rocks" for a in relevant)


def test_no_locations_uses_zero_distance():
    """GatherAction with no locations: distance defaults to 0, selection still works."""
    gd = _gd_two_sources()
    state = make_state(skills={"mining": 5})
    goal = GatherMaterialsGoal(target_item="copper_ore", needed={"copper_ore": 10})
    # rich_rocks rate=1, poor_rocks rate=3; no locations on either → distance=0 tie-break → code "poor_rocks" > "rich_rocks" → rich_rocks wins
    actions = [
        GatherAction(resource_code="rich_rocks", locations=frozenset()),
        GatherAction(resource_code="poor_rocks", locations=frozenset()),
    ]
    relevant = goal.relevant_actions(actions, state, gd)
    codes = {a.resource_code for a in relevant if isinstance(a, GatherAction)}
    assert codes == {"rich_rocks"}, f"yield-optimal source only, got {codes}"


def test_unknown_drop_table_fail_open():
    """If one resource's drop table is missing the item, no narrowing occurs (both survive)."""
    gd = GameData()
    # Both resources claim copper_ore as primary drop, but poor_rocks has no drop-table entry.
    gd._resource_drops = {"rich_rocks": "copper_ore", "poor_rocks": "copper_ore"}
    gd._resource_drops_full = {
        "rich_rocks": [("copper_ore", 1, 1, 1)],
        # poor_rocks has an empty drop table (unknown)
        "poor_rocks": [],
    }
    gd._resource_skill = {"rich_rocks": ("mining", 1), "poor_rocks": ("mining", 1)}
    state = make_state(skills={"mining": 5})
    goal = GatherMaterialsGoal(target_item="copper_ore", needed={"copper_ore": 10})
    actions = [
        GatherAction(resource_code="rich_rocks", locations=frozenset([(1, 0)])),
        GatherAction(resource_code="poor_rocks", locations=frozenset([(1, 0)])),
    ]
    relevant = goal.relevant_actions(actions, state, gd)
    codes = {a.resource_code for a in relevant if isinstance(a, GatherAction)}
    # fail-open: both survive when the drop table is incomplete
    assert codes == {"rich_rocks", "poor_rocks"}, f"expected both to survive, got {codes}"

"""Which gather sources `GatherMaterialsGoal.relevant_actions` admits when a
drop has skill-gated sources: an open source displaces a locked one, and a
source gated above the server skill ceiling is never admitted."""

from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective


def _gd_gated_gather() -> GameData:
    """A closure whose only material is a resource gated behind a GATHER skill
    the character is under (deep_ore ← deep_rocks, mining 10). Mirrors iron_ore
    ← iron_rocks in the l12_taskgated_bag scenario: the sole ore source is
    skill-locked, so the only route is the mining grind, then Gather."""
    gd = GameData()
    gd._item_stats = {
        "deep_ore": ItemStats(code="deep_ore", level=10, type_="resource",
                              subtype="mining"),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource",
                                subtype="mining"),
    }
    gd._crafting_recipes = {}
    # copper_rocks (mining 1) is the low grindable rung the mining grind climbs
    # from; deep_rocks (mining 10) is the skill-locked target source.
    gd._resource_drops = {"deep_rocks": "deep_ore", "copper_rocks": "copper_ore"}
    gd._resource_skill = {"deep_rocks": ("mining", 10), "copper_rocks": ("mining", 1)}
    gd._resource_locations = {"deep_rocks": [(3, 3)], "copper_rocks": [(4, 4)]}
    gd._workshop_locations = {}
    gd._bank_location = (0, 0)
    gd._taskmaster_location = (1, 1)
    return gd


def test_open_source_displaces_locked_no_forced_grind() -> None:
    """When a drop has BOTH an open source and a skill-locked one, admit only the
    open source — never force a grind for a workable material (the fishing-40
    salmon vs fishing-30 bass narrowing hazard)."""
    gd = _gd_gated_gather()
    # shallow_rocks (mining 1, OPEN) also drops deep_ore — a workable source now.
    gd._item_stats["deep_ore"] = ItemStats(code="deep_ore", level=1,
                                            type_="resource", subtype="mining")
    gd._resource_drops["shallow_rocks"] = "deep_ore"
    gd._resource_skill["shallow_rocks"] = ("mining", 1)
    gd._resource_locations["shallow_rocks"] = [(5, 5)]
    state = scenario_state(
        ScenarioCharacter(name="t", level=12, skills={"mining": 1}), gd)
    objective = CharacterObjective.from_game_data(gd)
    actions = build_actions(gd, state, objective, bank_accessible=True,
                            task_exchange_min_coins=0)
    goal = GatherMaterialsGoal(target_item="deep_ore", needed={"deep_ore": 1})

    admitted = goal.relevant_actions(actions, state, gd)
    assert any(isinstance(a, GatherAction) and a.resource_code == "shallow_rocks"
               for a in admitted), "open shallow_rocks must be admitted"
    assert not any(isinstance(a, GatherAction) and a.resource_code == "deep_rocks"
                   for a in admitted), "locked deep_rocks must NOT displace open source"


def test_gather_gate_above_ceiling_stays_excluded() -> None:
    """A source gated ABOVE the server skill ceiling has no grind route, so it
    stays excluded (preserving _skill_open's permanently-closed exclusion)."""
    gd = _gd_gated_gather()
    gd._resource_skill["deep_rocks"] = ("mining", gd.max_skill_level + 5)
    state = scenario_state(
        ScenarioCharacter(name="t", level=12, skills={"mining": 1}), gd)
    objective = CharacterObjective.from_game_data(gd)
    actions = build_actions(gd, state, objective, bank_accessible=True,
                            task_exchange_min_coins=0)
    goal = GatherMaterialsGoal(target_item="deep_ore", needed={"deep_ore": 1})

    admitted = goal.relevant_actions(actions, state, gd)
    assert not any(isinstance(a, GatherAction) and a.resource_code == "deep_rocks"
                   for a in admitted), "above-ceiling gather has no route — excluded"

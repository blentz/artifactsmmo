"""A skill gate on a closure is a SUB-TASK (Phase 2d-a of
docs/PLAN_decision_architecture_redesign.md): decomposition expands it into the
grind's own first real legs, not a `LevelSkill` macro leg that a second planner
expanded at execution. The walk opens a gate only when the skill can be ground
from here (`skill_is_grindable`), and declines, naming the item, when it
cannot."""

from datetime import UTC, datetime

from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.craft_plan_gen import DECOMPOSE_POLICY, decompose
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.reach_skill import ReachSkillGoal
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_craft_plan_gen import _copper_ring_actions, _ctx, _gd_copper_ring


def _gd() -> GameData:
    """widget (gearcrafting lv5) / trinket (gearcrafting lv1), both made from
    gear_ore — a gatherable raw. Mirrors test_factory_level_skill.py's
    fixture, plus a resource-drop mapping so gear_ore is a gatherable ITEM
    (not just a leaf with no recipe): the CAN-GENERATE closure walk needs
    every non-craftable leaf to resolve as gatherable or dropped, else it
    returns None before ever reaching the skill gate for widget itself."""
    gd = GameData()
    gd._item_stats = {
        "widget": ItemStats(code="widget", level=5, type_="resource",
                            subtype="craft", crafting_skill="gearcrafting",
                            crafting_level=5),
        "trinket": ItemStats(code="trinket", level=1, type_="resource",
                             subtype="craft", crafting_skill="gearcrafting",
                             crafting_level=1),
        "gear_ore": ItemStats(code="gear_ore", level=1, type_="resource",
                              subtype="mob"),
    }
    gd._crafting_recipes = {"widget": {"gear_ore": 2}, "trinket": {"gear_ore": 1}}
    gd._resource_drops = {"gear_ore_rocks": "gear_ore"}
    gd._resource_locations = {"gear_ore_rocks": [(3, 3)]}
    gd._workshop_locations = {"gearcrafting": (2, 2)}
    gd._bank_location = (1, 1)
    gd._taskmaster_location = (0, 0)
    fill_monster_stat_defaults(gd)
    return gd


class TestASkillGateIsASubTask:

    def test_a_gate_no_grind_can_open_is_infeasible(self) -> None:
        """Without a craftable in-skill rung (trinket gone) and no gather arm
        (gearcrafting is not a gathering skill), the gate cannot open: the goal
        is infeasible and the decline names it."""
        gd = _gd()
        del gd._crafting_recipes["trinket"]
        del gd._item_stats["trinket"]
        state = make_state(inventory={}, bank_items={}, skills={"gearcrafting": 1})
        actions = build_actions(gd, state, CharacterObjective.from_game_data(gd),
                                bank_accessible=True, task_exchange_min_coins=0)
        declined: list[str] = []

        assert decompose(GatherMaterialsGoal("widget", {"widget": 1}), state, gd, actions,
                         _ctx(), declined) is None
        assert declined == ["infeasible:widget:no_route:widget"]


class TestTheGrindDecomposition:
    def test_a_skill_at_its_target_is_satisfied(self) -> None:
        declined: list[str] = []
        state = make_state(skills={"gearcrafting": 5})
        assert decompose(ReachSkillGoal("gearcrafting", 5), state, _gd(), [], _ctx(), declined) is None
        assert declined == ["satisfied"]

    def test_the_legs_before_a_gate_whose_grind_declines_still_run(self) -> None:
        """Five banked ore cover half the goal; the rest needs mining 10,
        and the mining grind's own rung (the bar) needs that same ore, so the
        sub-task declines. The withdraw is still progress and runs; the next
        cycle replans from there."""
        gd = _gd_copper_ring()
        gd._resource_skill = {"copper_rocks": ("mining", 10)}
        state = make_state(inventory={}, bank_items={"copper_ore": 5},
                           skills={"mining": 5, "jewelrycrafting": 5})
        declined: list[str] = []
        legs = decompose(GatherMaterialsGoal("copper_ore", {"copper_ore": 10}), state, gd,
                         _copper_ring_actions(), _ctx(), declined)
        assert [repr(a) for a in legs or []] == ["Withdraw(copper_ore×5)"]
        assert declined == ["infeasible:copper_bar:no_route:"]


class TestAGrindCycleEndsInItsEarningLeg:
    def test_the_grind_plans_its_rung_through_the_craft_that_earns(self) -> None:
        """Phase 2d-L3: one grind cycle is the whole committed plan for ANOTHER
        rung, ending in the craft that pays the skill's XP."""
        gd = _gd()
        state = make_state(inventory={}, bank_items={}, skills={"gearcrafting": 1})
        actions = build_actions(gd, state, CharacterObjective.from_game_data(gd),
                                bank_accessible=True, task_exchange_min_coins=0)
        legs = decompose(ReachSkillGoal("gearcrafting", 2), state, gd, actions, _ctx())
        assert [repr(a) for a in legs or []] == ["Gather(gear_ore_rocks×1)", "Craft(trinket×1)"]

    def test_a_produced_rung_keeps_only_the_routes_that_earn(self, monkeypatch) -> None:
        """A rung a vendor sells would count toward the goal and earn nothing:
        produced, it keeps its CRAFT (or GATHER) routes only."""
        gd = _gd()
        monkeypatch.setattr(gd, "npc_purchases",
                            lambda code: [("vendor", 1, "gold")] if code == "trinket" else [])
        monkeypatch.setattr(gd, "npc_location", lambda npc: (5, 5))
        state = make_state(inventory={}, bank_items={"trinket": 3}, skills={"gearcrafting": 1},
                           gold=1000)
        model = ObtainModel(state, gd, _ctx(), datetime.now(UTC))
        held = model.walk_graph("trinket", DECOMPOSE_POLICY)
        assert {r.kind for r in held.sources["trinket"]} >= {SourceKind.CRAFT, SourceKind.BUY}
        made = model.walk_graph("trinket", DECOMPOSE_POLICY, produce=frozenset({"trinket"}))
        assert {r.kind for r in made.sources["trinket"]} == {SourceKind.CRAFT}

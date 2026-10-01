"""A grind's fight leg stocks heals first (`grind_heal_prep`, and its hook in
`craft_plan_gen._decompose_grind`).

Live C3P0 2026-09-28: a gearcrafting grind fed by fights cost 120 hp a fight,
and RestoreHP bought the food back one unit at a time, `Craft(cheese×1)` + eat
before every fight. The fight leg now obtains a batch sized to the stock target
first, through the same decomposition every grind leg uses."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch

from artifactsmmo_cli.ai import craft_plan_gen
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.consumable_supply import HEAL_STOCK_FLOOR
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.reach_skill import ReachSkillGoal
from artifactsmmo_cli.ai.grind_heal_prep import heal_prep_goal
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import LEGACY
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai._monster_fixture import fill_monster_stat_defaults


def _gd() -> GameData:
    """A gearcrafting rung fed by a monster drop, and a craftable heal."""
    gd = GameData()
    gd._item_stats = {
        "trinket": ItemStats(code="trinket", level=1, type_="resource", subtype="craft",
                             crafting_skill="gearcrafting", crafting_level=1),
        "pelt": ItemStats(code="pelt", level=1, type_="resource", subtype="mob"),
        "cheese": ItemStats(code="cheese", level=1, type_="consumable", hp_restore=150,
                            crafting_skill="cooking", crafting_level=1),
        "milk": ItemStats(code="milk", level=1, type_="resource", subtype="mob"),
    }
    gd._crafting_recipes = {"trinket": {"pelt": 1}, "cheese": {"milk": 1}}
    gd._workshop_locations = {"gearcrafting": (2, 2), "cooking": (4, 4)}
    return gd


def _state(gd: GameData, inventory: dict[str, int],
           bank: dict[str, int] | None = None) -> WorldState:
    state = scenario_state(
        ScenarioCharacter(name="hero", level=5, skills={"gearcrafting": 1, "cooking": 1}), gd)
    return replace(state, inventory=inventory, bank_items=bank if bank is not None else {})


class TestHealPrepGoal:
    def test_no_goal_when_the_stock_is_met(self):
        gd = _gd()
        assert heal_prep_goal(_state(gd, {"cheese": HEAL_STOCK_FLOOR}), gd, NO_PROFILE_CONTEXT) is None

    def test_no_goal_when_no_heal_can_be_crafted(self):
        gd = _gd()
        state = replace(_state(gd, {"milk": 10}), skills={"gearcrafting": 1, "cooking": 0})
        assert heal_prep_goal(state, gd, NO_PROFILE_CONTEXT) is None

    def test_no_goal_when_no_heal_can_be_supplied(self):
        """Milk has no route: with none held, no cheese batch can be made."""
        gd = _gd()
        assert heal_prep_goal(_state(gd, {}), gd, NO_PROFILE_CONTEXT) is None

    def test_no_goal_when_the_heal_needs_a_fight(self):
        """Milk drops from a cow the character can beat, but the prep never
        fights for its ingredients: the fight costs the hp the stock saves."""
        gd = _gd()
        gd._monster_level = {"cow": 1}
        gd._monster_hp = {"cow": 60}
        gd._monster_attack = {"cow": {"air": 4}}
        gd._monster_drops = {"cow": [("milk", 1, 1, 1)]}
        gd._monster_locations = {"cow": [(0, 1)]}
        fill_monster_stat_defaults(gd)
        state = replace(_state(gd, {}), hp=165, max_hp=165, attack={"air": 5}, dmg=18)
        assert ObtainModel(state, gd, NO_PROFILE_CONTEXT, datetime.now(UTC)).feasible(
            "cheese", HEAL_STOCK_FLOOR, LEGACY)
        assert heal_prep_goal(state, gd, NO_PROFILE_CONTEXT) is None

    def test_the_strongest_heal_that_can_be_supplied_wins(self):
        """Live C3P0: the strongest heal on skill alone (`apple_pie`) could not
        be supplied while `cheese` could. A prep for an unsuppliable heal would
        never decompose, so the choice asks the obtain model first."""
        gd = _gd()
        gd._item_stats["pie"] = ItemStats(code="pie", level=1, type_="consumable",
                                          hp_restore=300, crafting_skill="cooking",
                                          crafting_level=1)
        gd._item_stats["apple"] = ItemStats(code="apple", level=1, type_="resource")
        gd._crafting_recipes["pie"] = {"apple": 1}
        goal = heal_prep_goal(_state(gd, {"milk": 10}), gd, NO_PROFILE_CONTEXT)
        assert isinstance(goal, GatherMaterialsGoal)
        assert list(goal.needed) == ["cheese"]
        goal = heal_prep_goal(_state(gd, {"milk": 10, "apple": 10}), gd, NO_PROFILE_CONTEXT)
        assert isinstance(goal, GatherMaterialsGoal)
        assert list(goal.needed) == ["pie"]

    def test_the_batch_is_the_deficit_on_top_of_the_bag(self):
        """Two in the bag: the goal asks for the bag's two plus the deficit."""
        gd = _gd()
        goal = heal_prep_goal(_state(gd, {"cheese": 2, "milk": 10}, bank={"cheese": 1}), gd,
                              NO_PROFILE_CONTEXT)
        assert isinstance(goal, GatherMaterialsGoal)
        assert goal.needed == {"cheese": 2 + (HEAL_STOCK_FLOOR - 2)}

    def test_a_banked_heal_is_withdrawn_before_crafting(self):
        """Real decomposition (the one walk): the banked cheese is withdrawn into
        the bag and only the rest is crafted, so the bag reaches the stock
        target exactly."""
        gd = _gd()
        gd._bank_location = (5, 5)
        state = _state(gd, {"cheese": 2, "milk": 10}, bank={"cheese": 1})
        goal = heal_prep_goal(state, gd, NO_PROFILE_CONTEXT)
        assert goal is not None
        actions = [CraftAction(code="cheese", workshop_location=(4, 4))]
        plan = decompose(goal, state, gd, actions, NO_PROFILE_CONTEXT)
        assert plan is not None
        assert [(type(a).__name__, a.code, a.quantity) for a in plan] == [
            ("WithdrawItemAction", "cheese", 1),
            ("CraftAction", "cheese", HEAL_STOCK_FLOOR - 2 - 1),
        ]


_FIGHT = FightAction(monster_code="wolf", locations=frozenset({(1, 1)}))
_GRIND_GOAL = GatherMaterialsGoal(target_item="pelt", needed={"pelt": 1}, skill_grind=True)
_CHEESE = CraftAction(code="cheese", workshop_location=(4, 4))


def _grind(inventory: dict[str, int], grind_leg, prep=None) -> tuple[list | None, list[str]]:
    """Decompose one gearcrafting grind whose rung walk yields `grind_leg`
    (one leg, or a list of them).
    The heal prep runs the real walk over a craftable cheese unless `prep`
    stands in for its decomposition. Returns (legs, declines)."""
    gd = _gd()
    state = _state(gd, inventory)
    real_walk = craft_plan_gen._walk_plan

    def walk(goal, *args):
        if goal is not _GRIND_GOAL:
            return real_walk(goal, *args)
        return list(grind_leg) if isinstance(grind_leg, list) else [grind_leg]

    declined: list[str] = []
    with patch.object(craft_plan_gen, "grind_rung_goal", return_value=_GRIND_GOAL), \
            patch.object(craft_plan_gen, "_walk_plan", side_effect=walk):
        if prep is None:
            legs = decompose(ReachSkillGoal("gearcrafting", 5), state, gd, [_CHEESE],
                             NO_PROFILE_CONTEXT, declined)
        else:
            with patch.object(craft_plan_gen, "decompose", side_effect=prep):
                legs = craft_plan_gen._decompose_grind("gearcrafting", 5, state, gd, [_CHEESE],
                                                       NO_PROFILE_CONTEXT, declined, frozenset())
    return legs, declined


class TestGrindFightLegPreps:
    """The prep lives in the grind's decomposition (Phase 2d-a), so the arbiter's
    ReachSkill candidate and the LevelSkill expansion both get it."""

    def test_an_understocked_fight_leg_crafts_the_heal_batch_first(self):
        legs, declined = _grind({"milk": 10}, _FIGHT)
        assert legs is not None
        assert [(type(a).__name__, getattr(a, "quantity", None)) for a in legs] == [
            ("CraftAction", HEAL_STOCK_FLOOR), ("FightAction", None)]
        assert declined == []

    def test_a_prep_decline_is_noted_and_the_fight_goes_ahead(self):
        def declines(_goal, _state, _gd, _actions, _ctx, declined, subtasks):
            declined.append("unmapped_step:milk")
            return None

        legs, declined = _grind({"milk": 10}, _FIGHT, prep=declines)
        assert legs == [_FIGHT]
        assert declined == ["heal_prep:unmapped_step:milk"]

    def test_a_stocked_fight_leg_fights(self):
        assert _grind({"cheese": HEAL_STOCK_FLOOR}, _FIGHT) == ([_FIGHT], [])

    def test_the_fight_goes_ahead_when_the_prep_would_fight(self):
        """The prep never fights for its ingredients: the fight it would add
        costs the hp the stock is meant to save."""
        other = FightAction(monster_code="cow", locations=frozenset({(6, 6)}))
        assert _grind({"milk": 10}, _FIGHT, prep=lambda *_a, **_k: [other])[0] == [_FIGHT]

    def test_a_fight_after_a_gather_is_prepped_too(self):
        """The plan is committed (Phase 2d-L1c), so a fight later in it runs
        this cycle and the heal stock is made first."""
        gather = GatherAction(resource_code="milk_rocks", locations=frozenset({(3, 3)}))
        legs, declined = _grind({"milk": 10}, [gather, _FIGHT])
        assert legs is not None
        assert [type(a).__name__ for a in legs] == ["CraftAction", "GatherAction", "FightAction"]
        assert declined == []

    def test_a_gather_leg_is_not_prepped(self):
        """Only a fight costs hp; a gather leg runs as planned."""
        gather = GatherAction(resource_code="milk_rocks", locations=frozenset({(3, 3)}))
        assert _grind({"milk": 10}, gather) == ([gather], [])

"""A grind's fight leg stocks heals first (`grind_heal_prep`, and its hook in
`GamePlayer._execute_level_skill`).

Live C3P0 2026-09-28: a gearcrafting grind fed by fights cost 120 hp a fight,
and RestoreHP bought the food back one unit at a time, `Craft(cheese×1)` + eat
before every fight. The fight leg now obtains a batch sized to the stock target
first, through the same decomposition every grind leg uses."""

from dataclasses import replace
from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.consumable_supply import HEAL_STOCK_FLOOR
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.decision_mechanism import Mechanism
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.grind_heal_prep import heal_prep_goal
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.world_state import WorldState


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

    def test_the_batch_counts_the_banks_copies(self):
        """Two in the bag, one in the bank: the goal asks for bank + bag +
        deficit, because decomposition credits the banked copy of the target
        without withdrawing it (next test)."""
        gd = _gd()
        goal = heal_prep_goal(_state(gd, {"cheese": 2, "milk": 10}, bank={"cheese": 1}), gd,
                              NO_PROFILE_CONTEXT)
        assert isinstance(goal, GatherMaterialsGoal)
        assert goal.needed == {"cheese": 1 + 2 + (HEAL_STOCK_FLOOR - 2)}

    def test_the_plan_crafts_exactly_what_the_bag_lacks(self):
        """Real decomposition: a banked copy is credited, not withdrawn, so
        the craft must still cover the whole deficit for the bag to reach the
        stock target."""
        gd = _gd()
        gd._bank_location = (5, 5)
        state = _state(gd, {"cheese": 2, "milk": 10}, bank={"cheese": 1})
        goal = heal_prep_goal(state, gd, NO_PROFILE_CONTEXT)
        assert goal is not None
        actions = [CraftAction(code="cheese", workshop_location=(4, 4))]
        plan = decompose(goal, state, gd, actions, NO_PROFILE_CONTEXT)
        assert plan is not None
        assert [(type(a).__name__, a.code, a.quantity) for a in plan] == [
            ("CraftAction", "cheese", HEAL_STOCK_FLOOR - 2),
        ]


def _player(inventory: dict[str, int]) -> GamePlayer:
    gd = _gd()
    player = GamePlayer(character="hero")
    player.game_data = gd
    player.state = _state(gd, inventory)
    return player


_FIGHT = FightAction(monster_code="wolf", locations=frozenset({(1, 1)}))
_GRIND_GOAL = GatherMaterialsGoal(target_item="pelt", needed={"pelt": 1}, skill_grind=True)


def _run_grind(player: GamePlayer, grind_leg, prep_plan):
    """Expand one LevelSkill whose grind leg is `grind_leg`; the grind goal's
    decomposition declines (so the planner supplies the leg) and the prep's
    returns `prep_plan`. Returns the leg that was executed."""
    executed = []

    def fake_execute(leg, _client):
        executed.append(leg)
        return player.state, "ok", leg

    decompose_answers = iter([None, prep_plan])
    with patch.object(player, "_build_actions", return_value=[]), \
            patch("artifactsmmo_cli.ai.player.next_grind_goal", return_value=_GRIND_GOAL), \
            patch("artifactsmmo_cli.ai.player.decompose",
                  side_effect=lambda *_a: next(decompose_answers)), \
            patch.object(player.planner, "plan", return_value=[grind_leg]), \
            patch.object(player, "_execute", side_effect=fake_execute):
        player._execute_level_skill(LevelSkill("gearcrafting", 5), MagicMock())
    return executed


class TestGrindFightLegPreps:
    def test_an_understocked_fight_leg_crafts_the_heal_batch_first(self):
        player = _player({"milk": 10})
        craft = CraftAction(code="cheese", quantity=HEAL_STOCK_FLOOR, workshop_location=(4, 4))
        executed = _run_grind(player, _FIGHT, [craft])
        assert executed == [craft]
        assert player._last_grind_leg is craft
        noted = player._events.drain()
        prep = heal_prep_goal(player.state, player.game_data, NO_PROFILE_CONTEXT)
        assert (Mechanism.FAST_PATH, repr(prep),
                "grind heal prep plan_len=1") in noted

    def test_a_prep_decline_is_noted_and_the_fight_goes_ahead(self):
        player = _player({"milk": 10})
        executed = []

        def declines(goal, state, game_data, actions, ctx, declined=None):
            if declined is not None and isinstance(goal, GatherMaterialsGoal) and "cheese" in goal.needed:
                declined.append("no_source:milk")
                return None
            return None

        with patch.object(player, "_build_actions", return_value=[]), \
                patch("artifactsmmo_cli.ai.player.next_grind_goal", return_value=_GRIND_GOAL), \
                patch("artifactsmmo_cli.ai.player.decompose", side_effect=declines), \
                patch.object(player.planner, "plan", return_value=[_FIGHT]), \
                patch.object(player, "_execute",
                             side_effect=lambda leg, _c: executed.append(leg) or (player.state, "ok", leg)):
            player._execute_level_skill(LevelSkill("gearcrafting", 5), MagicMock())
        assert executed == [_FIGHT]
        prep = heal_prep_goal(player.state, player.game_data, NO_PROFILE_CONTEXT)
        assert (Mechanism.DECOMPOSE_DECLINE, repr(prep), "no_source:milk") in player._events.drain()

    def test_a_stocked_fight_leg_fights(self):
        player = _player({"cheese": HEAL_STOCK_FLOOR})
        assert _run_grind(player, _FIGHT, None) == [_FIGHT]

    def test_the_fight_goes_ahead_when_the_prep_cannot_be_decomposed(self):
        """A heal stock saves requests; it must never block the grind it serves."""
        player = _player({"milk": 10})
        assert _run_grind(player, _FIGHT, None) == [_FIGHT]

    def test_the_fight_goes_ahead_when_the_prep_would_open_another_grind(self):
        player = _player({"milk": 10})
        assert _run_grind(player, _FIGHT, [LevelSkill("cooking", 2)]) == [_FIGHT]

    def test_a_gather_leg_is_not_prepped(self):
        """Only a fight costs hp; a gather leg runs as planned."""
        player = _player({"milk": 10})
        gather = GatherAction(resource_code="milk_rocks", locations=frozenset({(3, 3)}))
        craft = CraftAction(code="cheese", quantity=HEAL_STOCK_FLOOR, workshop_location=(4, 4))
        assert _run_grind(player, gather, [craft]) == [gather]

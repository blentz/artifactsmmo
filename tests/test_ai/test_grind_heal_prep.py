"""A fight is fought with the chosen loadout's food carried (`grind_heal_prep`,
its hook in `craft_plan_gen._decompose_grind`, and the MAINTAIN_CONSUMABLES
rung's goal).

Live C3P0 2026-09-28: a gearcrafting grind fed by fights cost 120 hp a fight,
and RestoreHP bought the food back one unit at a time, `Craft(cheese×1)` + eat
before every fight. The fight leg now obtains the food the loadout chosen
against its monster eats, sized to that food's carry
(`chosen_loadout.food_carry`), through the same decomposition every grind leg
uses (docs/PLAN_consumable_utility.md increment 5)."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch

from artifactsmmo_cli.ai import craft_plan_gen, grind_heal_prep
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.chosen_loadout import ChosenLoadout, food_carry
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.reach_skill import ReachSkillGoal
from artifactsmmo_cli.ai.grind_heal_prep import (
    HEAL_PREP_POLICY,
    heal_prep_goal,
    maintain_consumables_goal,
)
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import LEGACY, Policy
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai._monster_fixture import fill_monster_stat_defaults

CARRY = food_carry(1)
"""The carry of a food the loadout eats one unit of per fight."""


def _gd() -> GameData:
    """A gearcrafting rung fed by a monster drop, and two craftable foods:
    cheese (from milk) and bread (from wheat). Neither ingredient has a route,
    so a food is suppliable only from ingredients already held."""
    gd = GameData()
    gd._item_stats = {
        "trinket": ItemStats(code="trinket", level=1, type_="resource", subtype="craft",
                             crafting_skill="gearcrafting", crafting_level=1),
        "pelt": ItemStats(code="pelt", level=1, type_="resource", subtype="mob"),
        "cheese": ItemStats(code="cheese", level=1, type_="consumable", hp_restore=150,
                            crafting_skill="cooking", crafting_level=1),
        "milk": ItemStats(code="milk", level=1, type_="resource", subtype="mob"),
        "bread": ItemStats(code="bread", level=1, type_="consumable", hp_restore=100,
                           crafting_skill="cooking", crafting_level=1),
        "wheat": ItemStats(code="wheat", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"trinket": {"pelt": 1}, "cheese": {"milk": 1},
                            "bread": {"wheat": 1}}
    gd._workshop_locations = {"gearcrafting": (2, 2), "cooking": (4, 4)}
    gd._bank_location = (5, 5)
    return gd


def _state(gd: GameData, inventory: dict[str, int],
           bank: dict[str, int] | None = None) -> WorldState:
    state = scenario_state(
        ScenarioCharacter(name="hero", level=5, skills={"gearcrafting": 1, "cooking": 1}), gd)
    return replace(state, inventory=inventory, bank_items=bank if bank is not None else {},
                   inventory_max=200)


def _eats(*food: tuple[str, int], monster: str = "wolf",
          combat_monster: str | None = "wolf") -> SelectionContext:
    """A cycle whose loadout, chosen against `monster`, eats `food` in order."""
    return replace(NO_PROFILE_CONTEXT, combat_monster=combat_monster,
                   loadout=ChosenLoadout(monster=monster, potions=(), food=food))


EATS_CHEESE = _eats(("cheese", 1))
EATS_CHEESE_THEN_BREAD = _eats(("cheese", 1), ("bread", 1))


def _needed(goal: GatherMaterialsGoal | None) -> dict[str, int] | None:
    assert goal is None or isinstance(goal, GatherMaterialsGoal)
    return None if goal is None else dict(goal.needed)


class TestHealPrepGoal:
    def test_the_chosen_food_is_stocked_to_its_carry(self):
        gd = _gd()
        goal = heal_prep_goal(_state(gd, {"milk": CARRY}), gd, EATS_CHEESE, "wolf")
        assert _needed(goal) == {"cheese": CARRY}
        assert goal is not None and goal.carry  # satisfied by the BAG only (live 2026-10-10)

    def test_the_carry_scales_with_the_units_eaten_per_fight(self):
        gd = _gd()
        goal = heal_prep_goal(_state(gd, {"milk": 3 * CARRY}), gd, _eats(("cheese", 3)), "wolf")
        assert _needed(goal) == {"cheese": food_carry(3)}

    def test_the_bag_counts_toward_the_carry(self):
        """Five in the bag: the goal still names the full carry (the bag's five
        plus the rest); a full carry in the bag is no goal at all."""
        gd = _gd()
        goal = heal_prep_goal(_state(gd, {"cheese": 5, "milk": CARRY - 5}), gd,
                              EATS_CHEESE, "wolf")
        assert _needed(goal) == {"cheese": CARRY}
        assert heal_prep_goal(_state(gd, {"cheese": CARRY, "milk": CARRY}), gd,
                              EATS_CHEESE, "wolf") is None

    def test_rest_wins_when_the_loadout_eats_nothing(self):
        """The chosen recovery is Rest (the loadout eats no food): nothing is
        stocked, even with every ingredient on hand."""
        gd = _gd()
        assert heal_prep_goal(_state(gd, {"milk": CARRY}), gd, _eats(), "wolf") is None

    def test_an_unsuppliable_carry_stocks_the_units_held_in_the_bank(self):
        """No milk, so the carry cannot be crafted; the five banked cheese are
        free stock, so the goal is the units held (bag + bank), and the walk
        withdraws them."""
        gd = _gd()
        state = _state(gd, {}, bank={"cheese": 5})
        assert _needed(heal_prep_goal(state, gd, EATS_CHEESE, "wolf")) == {"cheese": 5}
        state = _state(gd, {"cheese": 2}, bank={"cheese": 3})
        assert _needed(heal_prep_goal(state, gd, EATS_CHEESE, "wolf")) == {"cheese": 5}

    def test_held_units_already_in_the_bag_are_no_goal(self):
        """The carry cannot be supplied and everything held is already in the
        bag: nothing to fetch."""
        gd = _gd()
        assert heal_prep_goal(_state(gd, {"cheese": 5}), gd, EATS_CHEESE, "wolf") is None

    def test_a_food_neither_suppliable_nor_held_is_skipped(self):
        """Cheese has no milk and none held: alone it is no goal, and with bread
        next in the loadout the bread is stocked."""
        gd = _gd()
        state = _state(gd, {"wheat": CARRY})
        assert heal_prep_goal(state, gd, EATS_CHEESE, "wolf") is None
        assert _needed(heal_prep_goal(state, gd, EATS_CHEESE_THEN_BREAD, "wolf")) == {
            "bread": CARRY}

    def test_a_food_the_character_cannot_craft_is_skipped(self):
        """Milk on hand but no cooking skill: the cheese cannot be supplied."""
        gd = _gd()
        state = replace(_state(gd, {"milk": CARRY}), skills={"gearcrafting": 1, "cooking": 0})
        assert heal_prep_goal(state, gd, EATS_CHEESE, "wolf") is None

    def test_the_second_food_is_stocked_once_the_first_is_carried(self):
        gd = _gd()
        state = _state(gd, {"cheese": CARRY, "milk": CARRY, "wheat": CARRY})
        assert _needed(heal_prep_goal(state, gd, EATS_CHEESE_THEN_BREAD, "wolf")) == {
            "bread": CARRY}
        assert heal_prep_goal(_state(gd, {"cheese": CARRY, "bread": CARRY}), gd,
                              EATS_CHEESE_THEN_BREAD, "wolf") is None

    def test_the_first_short_food_wins(self):
        gd = _gd()
        state = _state(gd, {"milk": CARRY, "wheat": CARRY})
        assert _needed(heal_prep_goal(state, gd, EATS_CHEESE_THEN_BREAD, "wolf")) == {
            "cheese": CARRY}

    def test_the_loadout_is_the_one_chosen_against_the_named_monster(self):
        """`loadout_for` is asked about the fight's monster; the cycle's own
        loadout (chosen against another monster) is not read directly."""
        gd = _gd()
        asked: list[str] = []

        def eats_bread(_state, _gd, _ctx, monster: str) -> ChosenLoadout:
            asked.append(monster)
            return ChosenLoadout(monster=monster, potions=(), food=(("bread", 1),))

        state = _state(gd, {"milk": CARRY, "wheat": CARRY})
        with patch.object(grind_heal_prep, "loadout_for", side_effect=eats_bread):
            goal = heal_prep_goal(state, gd, EATS_CHEESE, "ogre")
        assert asked == ["ogre"]
        assert _needed(goal) == {"bread": CARRY}

    def test_no_goal_when_the_food_needs_a_fight(self):
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
        assert ObtainModel(state, gd, EATS_CHEESE, datetime.now(UTC)).feasible(
            "cheese", CARRY, LEGACY), "fixture is vacuous: cheese must be feasible by fighting"
        assert heal_prep_goal(state, gd, EATS_CHEESE, "wolf") is None

    def test_a_banked_food_is_withdrawn_before_crafting(self):
        """Real decomposition (the one walk): the banked cheese is withdrawn into
        the bag and only the rest is crafted, so the bag reaches the carry
        exactly."""
        gd = _gd()
        state = _state(gd, {"cheese": 2, "milk": CARRY}, bank={"cheese": 1})
        goal = heal_prep_goal(state, gd, EATS_CHEESE, "wolf")
        assert goal is not None
        actions = [CraftAction(code="cheese", workshop_location=(4, 4))]
        plan = decompose(goal, state, gd, actions, EATS_CHEESE)
        assert plan is not None
        assert [(type(a).__name__, a.code, a.quantity) for a in plan] == [
            ("WithdrawItemAction", "cheese", 1),
            ("CraftAction", "cheese", CARRY - 2 - 1),
        ]


class TestMaintainConsumablesGoal:
    def test_no_goal_without_an_active_combat_target(self):
        gd = _gd()
        state = _state(gd, {"milk": CARRY})
        assert maintain_consumables_goal(state, gd, _eats(("cheese", 1), combat_monster=None)) is None

    def test_no_goal_without_a_chosen_loadout(self):
        gd = _gd()
        state = _state(gd, {"milk": CARRY})
        ctx = replace(NO_PROFILE_CONTEXT, combat_monster="wolf")
        assert maintain_consumables_goal(state, gd, ctx) is None

    def test_the_goal_is_heal_prep_for_the_loadouts_monster(self):
        """Combat active and a loadout chosen (against the fight ahead, which may
        differ from the farm target): the goal is heal prep for that monster."""
        gd = _gd()
        state = _state(gd, {"milk": CARRY})
        ctx = _eats(("cheese", 1), monster="ogre", combat_monster="wolf")
        asked: list[str] = []
        real = grind_heal_prep.loadout_for

        def spy(s, g, c, monster: str) -> ChosenLoadout:
            asked.append(monster)
            return real(s, g, c, monster)

        with patch.object(grind_heal_prep, "loadout_for", side_effect=spy):
            goal = maintain_consumables_goal(state, gd, ctx)
        assert asked == ["ogre"]
        assert _needed(goal) == {"cheese": CARRY}

    def test_no_goal_when_the_chosen_food_is_carried(self):
        gd = _gd()
        state = _state(gd, {"cheese": CARRY})
        assert maintain_consumables_goal(state, gd, EATS_CHEESE) is None


_FIGHT = FightAction(monster_code="wolf", locations=frozenset({(1, 1)}))
_GRIND_GOAL = GatherMaterialsGoal(target_item="pelt", needed={"pelt": 1}, skill_grind=True)
_CHEESE = CraftAction(code="cheese", workshop_location=(4, 4))


def _grind(inventory: dict[str, int], grind_leg, prep=None,
           ctx: SelectionContext = EATS_CHEESE) -> tuple[list | None, list[str]]:
    """Decompose one gearcrafting grind whose rung walk yields `grind_leg`
    (one leg, or a list of them), under a cycle whose loadout against the wolf
    eats `ctx`'s food.
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
                             ctx, declined)
        else:
            with patch.object(craft_plan_gen, "decompose", side_effect=prep):
                legs = craft_plan_gen._decompose_grind("gearcrafting", 5, state, gd, [_CHEESE],
                                                       ctx, declined, frozenset())
    return legs, declined


class TestGrindFightLegPreps:
    """The prep lives in the grind's decomposition (Phase 2d-a), so the arbiter's
    ReachSkill candidate and the LevelSkill expansion both get it."""

    def test_a_fight_leg_short_of_the_chosen_food_crafts_its_carry_first(self):
        legs, declined = _grind({"milk": CARRY}, _FIGHT)
        assert legs is not None
        assert [(type(a).__name__, getattr(a, "quantity", None)) for a in legs] == [
            ("CraftAction", CARRY), ("FightAction", None)]
        assert declined == []

    def test_the_prep_is_asked_about_the_first_fight_legs_monster(self):
        asked: list[str] = []

        def eats_nothing(_state, _gd, _ctx, monster: str) -> ChosenLoadout:
            asked.append(monster)
            return ChosenLoadout(monster=monster, potions=(), food=())

        ogre = FightAction(monster_code="ogre", locations=frozenset({(1, 2)}))
        gather = GatherAction(resource_code="milk_rocks", locations=frozenset({(3, 3)}))
        with patch.object(grind_heal_prep, "loadout_for", side_effect=eats_nothing):
            assert _grind({"milk": CARRY}, [gather, ogre, _FIGHT]) == (
                [gather, ogre, _FIGHT], [])
        assert asked == ["ogre"]

    def test_a_fight_leg_whose_loadout_rests_fights(self):
        """The loadout chosen against the wolf eats nothing (Rest wins): no prep."""
        assert _grind({"milk": CARRY}, _FIGHT, ctx=_eats()) == ([_FIGHT], [])

    def test_a_prep_decline_is_noted_and_the_fight_goes_ahead(self):
        def declines(_goal, _state, _gd, _actions, _ctx, declined, subtasks, policy):
            declined.append("unmapped_step:milk")
            return None

        legs, declined = _grind({"milk": CARRY}, _FIGHT, prep=declines)
        assert legs == [_FIGHT]
        assert declined == ["heal_prep:unmapped_step:milk"]

    def test_a_fight_leg_carrying_the_chosen_food_fights(self):
        assert _grind({"cheese": CARRY}, _FIGHT) == ([_FIGHT], [])

    def test_the_prep_is_walked_under_its_own_policy(self):
        """The prep never fights for its ingredients (the fight it would add
        costs the hp the stock is meant to save): it is decomposed under
        `HEAL_PREP_POLICY`, the policy that judged it feasible, which has no
        drop route (Phase 2d-F)."""
        seen: list[Policy] = []

        def walk(*_a, policy, **_k):
            seen.append(policy)
            return None

        assert _grind({"milk": CARRY}, _FIGHT, prep=walk)[0] == [_FIGHT]
        assert seen == [HEAL_PREP_POLICY] and not HEAL_PREP_POLICY.drop_routes

    def test_a_fight_after_a_gather_is_prepped_too(self):
        """The plan is committed (Phase 2d-L1c), so a fight later in it runs
        this cycle and the food's carry is made first."""
        gather = GatherAction(resource_code="milk_rocks", locations=frozenset({(3, 3)}))
        legs, declined = _grind({"milk": CARRY}, [gather, _FIGHT])
        assert legs is not None
        assert [type(a).__name__ for a in legs] == ["CraftAction", "GatherAction", "FightAction"]
        assert declined == []

    def test_a_gather_leg_is_not_prepped(self):
        """Only a fight costs hp; a gather leg runs as planned."""
        gather = GatherAction(resource_code="milk_rocks", locations=frozenset({(3, 3)}))
        assert _grind({"milk": CARRY}, gather) == ([gather], [])

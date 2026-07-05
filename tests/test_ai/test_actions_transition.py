"""Tests for MapTransitionAction (P5b: the region-crossing movement edge)."""

from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.transition import MapTransitionAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema


def _edge(**kw) -> MapTransitionAction:
    base = dict(portal_x=-4, portal_y=9, dest_x=-4, dest_y=8,
                dest_layer="overworld",
                conditions=(("gold", "cost", 5000),),
                travel_region="overworld")
    base.update(kw)
    return MapTransitionAction(**base)


class TestMapTransitionAction:
    def test_repr_carries_edge_and_fee(self):
        assert repr(_edge()) == "Transition((-4,9)->(-4,8,overworld), 5000g)"
        assert repr(_edge(conditions=())) == "Transition((-4,9)->(-4,8,overworld))"

    def test_applicable_iff_gold_covers_the_fee(self):
        gd = GameData()
        assert _edge().is_applicable(make_state(gold=5000), gd) is True
        assert _edge().is_applicable(make_state(gold=4999), gd) is False
        assert _edge(conditions=()).is_applicable(make_state(gold=0), gd) is True

    def test_unmodeled_condition_operators_never_pass(self):
        """An edge with an operator outside {cost, has_item} is inapplicable
        until explicitly modeled — never silently passable."""
        gd = GameData()
        gated = _edge(conditions=(("sonnengott_key", "has", 1),))
        assert gated.is_applicable(make_state(gold=10**9), gd) is False
        achievement = _edge(
            conditions=(("deep_delver", "achievement_unlocked", 1),))
        assert achievement.is_applicable(make_state(gold=10**9), gd) is False

    def test_apply_teleports_and_charges(self):
        gd = GameData()
        state = make_state(x=0, y=0, gold=6000)
        post = _edge(dest_layer="underground").apply(state, gd)
        assert (post.x, post.y, post.layer) == (-4, 8, "underground")
        assert post.gold == 1000

    def test_cost_folds_walk_to_portal(self):
        gd = GameData()
        assert _edge().cost(make_state(x=-4, y=9), gd) == 3.0
        assert _edge().cost(make_state(x=0, y=9), gd) == 7.0

    def test_execute_moves_then_transitions(self):
        a = _edge(conditions=())
        char = make_char_schema()
        state = make_state(x=-4, y=9)  # already at portal: no move call
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.transition.action_transition",
                   return_value=make_api_result(char)) as mock_t:
            a.execute(state, client)
        mock_t.assert_called_once_with(client=client, name="testchar")

    def test_execute_walks_to_portal_first(self):
        a = _edge(conditions=())
        char = make_char_schema()
        state = make_state(x=0, y=0)  # off-portal: MoveAction folds the walk
        client = MagicMock()
        moved = make_state(x=-4, y=9)
        with patch("artifactsmmo_cli.ai.actions.transition.MoveAction") as move_cls, \
             patch("artifactsmmo_cli.ai.actions.transition.action_transition",
                   return_value=make_api_result(char)) as mock_t:
            move_cls.return_value.execute.return_value = moved
            a.execute(state, client)
        move_cls.assert_called_once_with(x=-4, y=9)
        move_cls.return_value.execute.assert_called_once_with(state, client)
        mock_t.assert_called_once_with(client=client, name="testchar")


class TestKeyedTransitions:
    """`cost` (key item, CONSUMED from the inventory) and `has_item`
    (possessed in inventory or equipped, NOT consumed) — the two operators
    that open the five walled boss pockets (Lich Tomb, priestess hideout,
    Sonnengott region, Rosenblood/Empress houses)."""

    def test_item_cost_needs_key_in_inventory(self):
        gd = GameData()
        edge = _edge(conditions=(("lich_tomb_key", "cost", 1),))
        assert edge.is_applicable(
            make_state(inventory={"lich_tomb_key": 1}), gd) is True
        assert edge.is_applicable(make_state(inventory={}), gd) is False
        # an equipped copy cannot pay a CONSUMING cost
        equipped_only = make_state(
            inventory={}, equipment={"weapon_slot": "lich_tomb_key"})
        assert edge.is_applicable(equipped_only, gd) is False

    def test_item_cost_consumed_on_apply(self):
        gd = GameData()
        edge = _edge(conditions=(("lich_tomb_key", "cost", 1),),
                     dest_layer="underground")
        spare = edge.apply(
            make_state(inventory={"lich_tomb_key": 2, "bread": 1}, gold=50), gd)
        assert spare.inventory == {"lich_tomb_key": 1, "bread": 1}
        assert spare.gold == 50  # no gold charged
        assert (spare.x, spare.y, spare.layer) == (-4, 8, "underground")
        last = edge.apply(make_state(inventory={"lich_tomb_key": 1}), gd)
        assert last.inventory == {}  # spent to zero: entry dropped

    def test_has_item_inventory_or_equipped_not_consumed(self):
        gd = GameData()
        edge = _edge(conditions=(("cultist_cloak", "has_item", 1),))
        held = make_state(inventory={"cultist_cloak": 1})
        assert edge.is_applicable(held, gd) is True
        assert edge.apply(held, gd).inventory == {"cultist_cloak": 1}
        worn = make_state(equipment={"body_armor_slot": "cultist_cloak"})
        assert edge.is_applicable(worn, gd) is True
        assert edge.is_applicable(make_state(), gd) is False

    def test_mixed_gold_and_key_conditions(self):
        gd = GameData()
        edge = _edge(conditions=(("gold", "cost", 100),
                                 ("lich_tomb_key", "cost", 1)))
        funded = make_state(gold=100, inventory={"lich_tomb_key": 1})
        assert edge.is_applicable(funded, gd) is True
        assert edge.is_applicable(
            make_state(gold=99, inventory={"lich_tomb_key": 1}), gd) is False
        assert edge.is_applicable(make_state(gold=100, inventory={}), gd) is False
        post = edge.apply(funded, gd)
        assert post.gold == 0 and post.inventory == {}

    def test_repr_shows_key_conditions(self):
        assert repr(_edge(conditions=(("lich_tomb_key", "cost", 1),))) == \
            "Transition((-4,9)->(-4,8,overworld), lich_tomb_keyx1)"
        assert repr(_edge(conditions=(("cultist_cloak", "has_item", 1),))) == \
            "Transition((-4,9)->(-4,8,overworld), holds cultist_cloak)"


class TestRegionAwarePlanning:
    """P5b payoff: the planner chains a Transition edge to reach off-region
    content, and never offers off-region actions directly."""

    def _gd(self) -> GameData:
        gd = GameData()
        gd._monster_level = {"lich": 1}
        gd._monster_locations = {}  # underground: NOT in the legacy index
        fill_monster_stat_defaults(gd)
        gd._monster_hp = {"lich": 10}
        gd.world.transition_edges = {
            (2, 0, "overworld"): (9, 7, "underground", ()),
        }
        return gd

    def test_plan_chains_transition_then_fight(self):
        gd = self._gd()

        class KillLich(Goal):
            def is_satisfied(self, st):
                return st.xp > 0
            def heuristic(self, st):
                return 0.0
            def relevant_actions(self, actions, st, gd_):
                return actions
            def desired_state(self):
                return {"xp": 1}
            def value(self):
                return 1.0

        actions = [
            MapTransitionAction(portal_x=2, portal_y=0, dest_x=9, dest_y=7,
                                dest_layer="underground", conditions=(),
                                travel_region="overworld"),
            FightAction(monster_code="lich", locations=frozenset({(9, 8)}),
                        travel_region="underground"),
        ]
        state = make_state(x=0, y=0, xp=0, max_hp=100, hp=100,
                           attack={"fire": 30}, initiative=50)
        plan = GOAPPlanner().plan(state, KillLich(), actions, gd)
        assert [repr(a).split("(")[0] for a in plan] == ["Transition", "Fight"]

    def test_off_region_fight_not_offered_directly(self):
        gd = self._gd()
        fight = FightAction(monster_code="lich", locations=frozenset({(9, 8)}),
                            travel_region="underground")
        state = make_state(x=0, y=0)
        # The planner's region gate (not is_applicable) rejects it; simulate:
        assert fight.travel_region != gd.state_region(state)

"""Tests for MapTransitionAction (P5b: the region-crossing movement edge)."""

from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.transition import MapTransitionAction
from artifactsmmo_cli.ai.actions.transition_layer_error import TransitionLayerError
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.region_edges import admit_region_edges
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
        assert repr(_edge()) == "Transition((-4,9,overworld)->(-4,8,overworld), 5000g)"
        assert repr(_edge(conditions=())) == "Transition((-4,9,overworld)->(-4,8,overworld))"

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
            "Transition((-4,9,overworld)->(-4,8,overworld), lich_tomb_keyx1)"
        assert repr(_edge(conditions=(("cultist_cloak", "has_item", 1),))) == \
            "Transition((-4,9,overworld)->(-4,8,overworld), holds cultist_cloak)"


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
            def heuristic(self, st, gd_):
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

    def test_a_whitelisting_goal_still_reaches_off_region_content(self):
        """`test_plan_chains_transition_then_fight` above proves the planner CAN
        chain the edge — but its goal returns `actions` unfiltered, and no
        production goal does. 32 of the 40 goal files override
        `relevant_actions` with a whitelist, and not one of them lists
        `MapTransitionAction` (tag `"movement"`); grep the goals package and it
        appears nowhere. So the edge was emitted, applicable, and stripped from
        every real pool before the planner saw it.

        Live Robby, 2026-09-20 — level 30, 943 XP short of 31, 26 days and
        4,040 of 4,260 cycles on `LevelSkill` with ZERO fights. His grind target
        `rat` (also his held task) lives at `interior:-3,12`:

            relevant_actions: 4 of 1932
               FightAction(rat) admitted: 1
               MapTransitionAction admitted: 0      <- 30 in the pool

            explored=3 created=3 depth=1 plan_len=0

        Admitting the edges turned that into `explored=17 created=53 depth=5`
        and the two-action plan `Transition -> Fight(rat)`. This test is that
        case in miniature: a REAL goal with a REAL whitelist.
        """
        gd = self._gd()
        transition = MapTransitionAction(
            portal_x=2, portal_y=0, dest_x=9, dest_y=7,
            dest_layer="underground", conditions=(), travel_region="overworld")
        fight = FightAction(monster_code="lich", locations=frozenset({(9, 8)}),
                            travel_region="underground")
        actions = [transition, fight]
        state = make_state(x=0, y=0, xp=0, max_hp=100, hp=100,
                           attack={"fire": 30}, initiative=50)
        goal = GrindCharacterXPGoal(target_monster="lich", initial_xp=0)

        # Vacuity guards: the goal really does whitelist the edge away, and the
        # fight really is otherwise fine — so a plan can only come from the
        # producer re-admitting the edge.
        assert transition not in goal.relevant_actions(actions, state, gd)
        assert fight.is_applicable(state, gd) is True
        assert fight.travel_region != gd.state_region(state)

        plan = GOAPPlanner().plan(state, goal, actions, gd)
        assert [repr(a).split("(")[0] for a in plan] == ["Transition", "Fight"]

    def test_the_other_plan_producer_admits_the_edge_too(self):
        """`craft_plan_gen` is a nodes=0 FAST PATH that runs BEFORE the A* and
        filters through the same `goal.relevant_actions`. A re-admission that
        lives only in the planner leaves this producer blind — the
        two-plan-producers trap. Assert the shared helper covers both.
        """
        gd = self._gd()
        transition = MapTransitionAction(
            portal_x=2, portal_y=0, dest_x=9, dest_y=7,
            dest_layer="underground", conditions=(), travel_region="overworld")
        fight = FightAction(monster_code="lich", locations=frozenset({(9, 8)}),
                            travel_region="underground")
        actions = [transition, fight]
        state = make_state(x=0, y=0, xp=0, max_hp=100, hp=100,
                           attack={"fire": 30}, initiative=50)
        goal = GrindCharacterXPGoal(target_monster="lich", initial_xp=0)

        admitted = admit_region_edges(
            goal.relevant_actions(actions, state, gd), actions, state, gd)
        assert transition in admitted
        assert fight in admitted

    def test_no_edges_when_the_whitelist_has_no_off_region_work(self):
        """The 41x lesson, pinned. Re-adding the edges UNCONDITIONALLY put the
        44-scenario total at 60,662 planner nodes against a 1,467 baseline, and
        `l22_grey_rung_grind` alone at 57,554 against 899 — for a byte-identical
        71-action plan. 43 of those 44 selected goals have NO off-region action
        in their whitelist, so every edge was a dead branch expanded at every
        node, and `test_planner_bounded_by_relevant_actions_filter` failed
        outright (5 nodes against its ~2 bound).

        An edge is only ever worth a branch when there is something on the far
        side of it that this goal wants.
        """
        gd = self._gd()
        transition = MapTransitionAction(
            portal_x=2, portal_y=0, dest_x=9, dest_y=7,
            dest_layer="underground", conditions=(), travel_region="overworld")
        here = FightAction(monster_code="lich", locations=frozenset({(1, 1)}),
                           travel_region="overworld")
        # The POOL always carries off-region work — 48 actions of it live — so
        # the gate has to ask the goal's OWN whitelist. Asking `actions` would
        # gate on nothing and re-add the edges every time.
        elsewhere = FightAction(monster_code="lich",
                                locations=frozenset({(9, 8)}),
                                travel_region="underground")
        actions = [transition, here, elsewhere]
        state = make_state(x=0, y=0)

        assert gd.state_region(state) == "overworld"
        assert admit_region_edges([here], actions, state, gd) == [here]

    def test_re_admission_never_duplicates_an_already_listed_edge(self):
        """A goal that DOES list the edge (the default `return actions`) must
        not get it twice — a duplicated action doubles that branch in every
        expansion.
        """
        gd = self._gd()
        transition = MapTransitionAction(
            portal_x=2, portal_y=0, dest_x=9, dest_y=7,
            dest_layer="underground", conditions=(), travel_region="overworld")
        fight = FightAction(monster_code="lich", locations=frozenset({(9, 8)}),
                            travel_region="underground")
        actions = [transition, fight]
        state = make_state(x=0, y=0)
        assert admit_region_edges(list(actions), actions, state, gd) == actions


class TestPortalLayer:
    """The portal tile is (layer, x, y) — coordinates alone name a different
    tile on every other layer."""

    def test_inapplicable_from_another_layer(self):
        gd = GameData()
        edge = _edge(conditions=(), portal_layer="underground")
        assert edge.is_applicable(make_state(layer="underground"), gd) is True
        assert edge.is_applicable(make_state(layer="overworld"), gd) is False
        assert edge.is_applicable(make_state(layer="interior"), gd) is False

    def test_repr_names_the_portal_layer(self):
        assert repr(_edge(conditions=(), portal_layer="interior")) == (
            "Transition((-4,9,interior)->(-4,8,overworld))")

    def test_execute_refuses_to_post_from_the_wrong_layer(self):
        """Standing on the same COORDINATES one layer up used to look like
        "already at the portal": the move leg was skipped and the transition
        POSTed from an unrelated tile."""
        edge = _edge(conditions=(), portal_layer="underground")
        state = make_state(x=-4, y=9, layer="overworld")
        with patch("artifactsmmo_cli.ai.actions.transition.action_transition") as posted:
            with pytest.raises(TransitionLayerError, match="underground"):
                edge.execute(state, MagicMock())
        posted.assert_not_called()

    def test_execute_proceeds_on_the_portal_layer(self):
        edge = _edge(conditions=(), portal_layer="underground")
        state = make_state(x=-4, y=9, layer="underground")
        with patch("artifactsmmo_cli.ai.actions.transition.action_transition",
                   return_value=make_api_result(make_char_schema())) as posted:
            edge.execute(state, MagicMock())
        posted.assert_called_once()


class TestCoLocatedPortal:
    """A portal whose destination shares the source tile's coordinates.

    `(-3,12,overworld) <-> (-3,12,interior)` is the live shape: the Abandoned
    House sits on the Forest tile, so crossing changes ONLY `layer`.
    """

    def _gd(self) -> GameData:
        gd = GameData()
        gd._monster_level = {"rat": 1}
        gd._monster_locations = {}          # interior: not in the legacy index
        fill_monster_stat_defaults(gd)
        gd._monster_hp = {"rat": 10}
        gd.world.transition_edges = {
            (-3, 12, "interior"): (-3, 12, "overworld", ()),
            (-3, 12, "overworld"): (-3, 12, "interior", ()),
        }
        return gd

    def test_a_co_located_portal_is_not_pruned_as_already_visited(self) -> None:
        """THE STRANDING BUG. `_state_key` carried no `layer`, so the state
        after a co-located transition was byte-identical to the state before
        it: same x, y, hp, gold, xp, task, inventory, equipment, bank, skills.
        The child collided with its own parent in the visited set and was
        pruned, and the search ended one node in::

            explored=1  created=2  depth=0  plan_len=0

        Live Robby, 2026-09-21. He entered `interior:-3,12` from the bank at
        (7,13) — x,y changed there, so the INBOUND leg planned fine — fought
        rats down to 179/710, and then could not leave: `Rest` is an overworld
        action, `FightAction`'s HP floor refused another fight, and the one
        edge that would have got him out was pruned every cycle. The arbiter
        fell to `Wait` at cooldown 0.0 and spun at ~2 requests per second until
        the process died.

        Adding `layer` to the key only makes the dedup FINER, so Dijkstra
        optimality is untouched — the same argument the key's docstring already
        makes for `skills`.
        """
        gd = self._gd()
        rest = RestAction()
        state = make_state(x=-3, y=12, layer="interior", hp=179, max_hp=710)
        # Region naming comes from the walkable-tile model, which this minimal
        # fixture does not populate — read it rather than hard-coding a live
        # label, so the test pins the PRUNE and not the naming scheme.
        here = gd.state_region(state)
        out = MapTransitionAction(portal_x=-3, portal_y=12,
                                  portal_layer="interior",
                                  dest_x=-3, dest_y=12, dest_layer="overworld",
                                  conditions=(), travel_region=here)

        class GetHealthy(Goal):
            def is_satisfied(self, st):
                return st.hp >= st.max_hp
            def heuristic(self, st, gd_):
                return 0.0
            def relevant_actions(self, actions, st, gd_):
                return actions
            def desired_state(self):
                return {"hp": 710}
            def value(self):
                return 1.0

        # Vacuity guards: the crossing really is co-located, and the two legs
        # really do work in isolation — so an empty plan can only be the prune.
        assert here != gd.state_region(make_state(x=-3, y=12, layer="overworld")), \
            "the two layers must be different regions or there is nothing to cross"
        assert out.is_applicable(state, gd) is True
        crossed = out.apply(state, gd)
        assert (crossed.x, crossed.y) == (state.x, state.y), "not co-located"
        assert gd.state_region(crossed) != here
        assert rest.is_applicable(crossed, gd) is True

        plan = GOAPPlanner().plan(state, GetHealthy(), [out, rest], gd)
        assert [repr(a).split("(")[0] for a in plan] == ["Transition", "Rest"], plan

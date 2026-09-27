"""The unified obtain model (Phase 1 of docs/PLAN_decision_architecture_redesign.md).

`obtain_sources` is now a view of this model under `LEGACY`, so
`tests/test_ai/test_obtain_sources.py` exercises it through that view. These
tests cover what that suite cannot: routes every scenario world lacks (two
buyers for one surplus item), the non-legacy policies, and `feasible`.
"""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_model.drop_routes import drop_routes
from artifactsmmo_cli.ai.obtain_model.feasibility import Feasibility
from artifactsmmo_cli.ai.obtain_model.gate import Gate, GateKind
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import LEGACY, Policy
from artifactsmmo_cli.ai.obtain_model.route import UNBOUNDED_CAPACITY, Route
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.world_state import GOLD_CODE, TASKS_COIN_CODE, WorldState

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"
NOW = datetime(2026, 9, 27, tzinfo=UTC)
OPEN = Policy(all_gather_routes=True, gather_skill_gate=True, craft_skill_gate=True,
              event_vendors=True,
              spawn_known=True, allow_grey=False, vendor_routes=True, ge_routes=True,
              task_rewards=True, fight_gold=True)


def census_items(gd: GameData) -> list[str]:
    """Every item code in the catalogue, plus gold (the SELL route's target)."""
    return [*sorted(gd.all_item_stats), GOLD_CODE]


def _ctx(bank_accessible: bool = True) -> SelectionContext:
    return SelectionContext(bank_accessible=bank_accessible, bank_required_level=0,
                            bank_unlock_monster=None, initial_xp=0,
                            task_exchange_min_coins=0, combat_monster=None)


@pytest.fixture(scope="module")
def world() -> tuple[WorldState, GameData]:
    gd = load_bundle_game_data(BUNDLE, with_ge_orders=True)
    return scenario_state(SCENARIOS["l20_band_entry"], gd), gd


def test_routes_are_memoised_per_item(world: tuple[WorldState, GameData]) -> None:
    state, gd = world
    model = ObtainModel(state, gd, _ctx(), NOW)
    assert model.routes("copper_bar") is model.routes("copper_bar")


def test_every_resource_that_drops_an_item_is_a_route_with_its_skill_gate(
        world: tuple[WorldState, GameData]) -> None:
    """D-A / D-B: legacy offered only the most frequent dropper and never checked
    the gathering skill. The model offers every dropper and records the gate."""
    state, gd = world
    item = next(i for i in sorted(gd.gatherable_drop_items())
                if len({res for res, table in gd.resource_drops_full.items()
                        for code, *_ in table if code == i}) > 1)
    routes = [r for r in ObtainModel(state, gd, _ctx(), NOW).routes(item)
              if r.kind is SourceKind.GATHER]
    assert len(routes) > 1
    assert sum(r.primary for r in routes) == 1 and routes[0].primary
    assert all(any(g.kind is GateKind.GATHER_SKILL for g in r.gates) for r in routes
               if gd.resource_skill_level(r.via) is not None)


def test_a_primary_only_resource_is_still_offered(world: tuple[WorldState, GameData]) -> None:
    """An item only the primary-drop map knows (absent from every full drop
    table) falls back to that map, as `resource_for_drop` does."""
    state, gd = world
    resource, item = "fallback_rocks", "fallback_ore"
    with (patch.object(GameData, "resource_drops_full", new={}),
          patch.object(GameData, "resource_drops", new={resource: item}),
          patch.object(GameData, "resource_skill_level", return_value=None)):
        [route] = ObtainModel(state, gd, _ctx(), NOW).routes(item)
    assert (route.kind, route.via, route.primary) == (SourceKind.GATHER, resource, True)
    assert [g.kind for g in route.gates] == [GateKind.SPAWN_LIVE, GateKind.SPAWN_KNOWN]


def test_an_underground_resource_is_a_known_spawn_but_not_a_live_one(
        world: tuple[WorldState, GameData]) -> None:
    """The action factory builds a GatherAction for a reachable underground tile,
    so `gold_rocks` (underground only in this world) is gatherable under the
    routable-spawn predicate, which the overworld-only live index cannot see."""
    state, gd = world
    assert not gd.all_resource_locations.get("gold_rocks")
    [route] = [r for r in ObtainModel(state, gd, _ctx(), NOW).routes("gold_ore")
               if r.kind is SourceKind.GATHER and r.via == "gold_rocks"]
    spawn = {g.kind: g.satisfied for g in route.gates}
    assert spawn[GateKind.SPAWN_KNOWN] and not spawn[GateKind.SPAWN_LIVE]
    ungated = replace(LEGACY, gather_skill_gate=False)  # the fixture's mining is below 30
    assert ungated.ready(route) and not replace(ungated, spawn_known=False).ready(route)
    # And a resource with no tile on any layer is known to neither predicate.
    [nowhere] = [r for r in ObtainModel(state, gd, _ctx(), NOW).routes("diamond_stone")
                 if r.kind is SourceKind.GATHER and r.via == "strange_rocks"]
    assert not any(g.satisfied for g in nowhere.gates
                   if g.kind in (GateKind.SPAWN_LIVE, GateKind.SPAWN_KNOWN))


class TestPolicy:
    def _route(self, kind: SourceKind, *gates: Gate, primary: bool = True) -> Route:
        return Route("x", kind, "v", 1, 1, gates, primary=primary)

    def test_the_gather_skill_gate_counts_only_when_enforced(self) -> None:
        """D-A: LEGACY (the executor's readiness) enforces it; a policy that
        treats the gate as grindable does not."""
        route = self._route(SourceKind.GATHER, Gate(GateKind.GATHER_SKILL, "mining", False, 10))
        assert not LEGACY.ready(route) and not OPEN.ready(route)
        assert replace(LEGACY, gather_skill_gate=False).ready(route)

    def test_the_craft_skill_gate_counts_only_when_enforced(self) -> None:
        route = self._route(SourceKind.CRAFT, Gate(GateKind.CRAFT_SKILL, "mining", False, 10))
        assert not LEGACY.ready(route) and replace(LEGACY, craft_skill_gate=False).ready(route)

    def test_a_non_primary_gather_route_needs_all_gather_routes(self) -> None:
        route = self._route(SourceKind.GATHER, primary=False)
        assert not LEGACY.admits(route) and OPEN.admits(route)

    def test_event_vendors_swap_permanence_for_tradeability(self) -> None:
        event_vendor_open_now = self._route(
            SourceKind.BUY, Gate(GateKind.VENDOR_PERMANENT, "npc", False),
            Gate(GateKind.VENDOR_TRADEABLE, "npc", True))
        assert not LEGACY.ready(event_vendor_open_now) and OPEN.ready(event_vendor_open_now)
        permanent_but_closed = self._route(
            SourceKind.BUY, Gate(GateKind.VENDOR_PERMANENT, "npc", True),
            Gate(GateKind.VENDOR_TRADEABLE, "npc", False))
        assert LEGACY.ready(permanent_but_closed) and not OPEN.ready(permanent_but_closed)

    @pytest.mark.parametrize("kind", [SourceKind.DROP, SourceKind.GATHER])
    def test_a_spawned_route_enforces_one_spawn_predicate_chosen_by_the_policy(
            self, kind: SourceKind) -> None:
        """D-D: a policy asks either for a live tile or for a routable spawn
        (LEGACY since D-D), for a monster and a resource alike."""
        live_tile = replace(LEGACY, spawn_known=False)
        layered_only = self._route(kind, Gate(GateKind.SPAWN_LIVE, "m", False),
                                   Gate(GateKind.SPAWN_KNOWN, "m", True))
        assert not live_tile.ready(layered_only) and LEGACY.ready(layered_only)
        live_only = self._route(kind, Gate(GateKind.SPAWN_LIVE, "m", True),
                                Gate(GateKind.SPAWN_KNOWN, "m", False))
        assert live_tile.ready(live_only) and not LEGACY.ready(live_only)

    def test_a_vendor_and_a_ge_order_are_switched_apart(self) -> None:
        buy, fill = self._route(SourceKind.BUY), self._route(SourceKind.GE_FILL)
        assert LEGACY.admits(buy) and LEGACY.admits(fill)
        no_vendor = replace(LEGACY, vendor_routes=False)
        no_ge = replace(LEGACY, ge_routes=False)
        assert not no_vendor.admits(buy) and no_vendor.admits(fill)
        assert no_ge.admits(buy) and not no_ge.admits(fill)

    def test_the_task_board_is_offered_only_when_task_rewards_are(self) -> None:
        route = self._route(SourceKind.TASK_REWARD)
        assert not LEGACY.admits(route) and OPEN.admits(route)

    def test_every_other_route_is_offered_under_every_policy(self) -> None:
        closed = replace(LEGACY, all_gather_routes=False, vendor_routes=False, ge_routes=False,
                         task_rewards=False, fight_gold=False)
        assert all(closed.admits(self._route(kind, primary=False)) for kind in SourceKind
                   if kind not in (SourceKind.GATHER, SourceKind.BUY, SourceKind.GE_FILL,
                                   SourceKind.TASK_REWARD, SourceKind.GOLD_DROP))

    def test_fight_gold_is_offered_only_when_asked_for(self) -> None:
        route = self._route(SourceKind.GOLD_DROP)
        assert not LEGACY.admits(route) and OPEN.admits(route)

    def test_a_grey_dropper_counts_only_when_grey_is_allowed(self) -> None:
        grey = self._route(SourceKind.DROP, Gate(GateKind.XP_POSITIVE, "m", False))
        assert LEGACY.ready(grey) and not OPEN.ready(grey)

    def test_both_spawn_predicates_gate_any_other_route_under_every_policy(self) -> None:
        for gate in (Gate(GateKind.SPAWN_LIVE, "x", False), Gate(GateKind.SPAWN_KNOWN, "x", False)):
            route = self._route(SourceKind.CRAFT, gate)
            assert not LEGACY.ready(route) and not OPEN.ready(route)

    def test_every_other_gate_is_always_enforced(self) -> None:
        route = self._route(SourceKind.DROP, Gate(GateKind.WINNABLE, "wolf", False))
        assert not LEGACY.ready(route) and not OPEN.ready(route)


def test_only_the_first_usable_buyer_of_a_surplus_item_is_a_ready_sell_route(
        world: tuple[WorldState, GameData]) -> None:
    """Buyers come highest price first; a closed first buyer yields to the next
    one, and a third buyer of the same item is never offered. The scenario
    worlds never hold a surplus with two buyers, so the census cannot see this."""
    state, gd = world
    buyers = [("closed_npc", 30), ("free_npc", 0), ("open_npc", 20), ("cheap_npc", 10)]
    with (patch("artifactsmmo_cli.ai.obtain_model.obtain_model.accumulation_sell.sellable_surplus",
                return_value={"relic": 3}),
          patch.object(GameData, "npcs_buying_item", return_value=buyers),
          patch.object(GameData, "npc_location", return_value=(0, 0)),
          patch("artifactsmmo_cli.ai.obtain_model.obtain_model.event_npc_tradeable",
                side_effect=lambda npc, *a, **kw: npc != "closed_npc")):
        model = ObtainModel(state, gd, _ctx(), NOW)
        routes = [r for r in model.routes(GOLD_CODE) if r.kind is SourceKind.SELL]
        ready = model.ready(GOLD_CODE, LEGACY)
    assert [r.agent for r in routes] == ["closed_npc", "open_npc", "cheap_npc"]  # price 0 is no route
    assert [(r.via, r.agent, r.yield_per, r.capacity) for r in ready] == [("relic", "open_npc", 20, 60)]


def test_an_unowned_non_gold_item_has_no_sell_route(world: tuple[WorldState, GameData]) -> None:
    state, gd = world
    assert not [r for r in ObtainModel(state, gd, _ctx(), NOW).routes("copper_ore")
                if r.kind is SourceKind.SELL]


def test_a_sleeping_monster_is_not_asked_whether_it_is_winnable(
        world: tuple[WorldState, GameData]) -> None:
    state, gd = world
    item = next(i for i in sorted(gd.all_item_stats) if gd.monsters_dropping(i))
    with (patch.object(GameData, "all_monster_locations", new={}),
          patch.object(GameData, "monster_spawn_known", return_value=False),
          patch("artifactsmmo_cli.ai.obtain_model.drop_routes.is_winnable") as winnable):
        routes = ObtainModel(state, gd, _ctx(), NOW).routes(item)
    winnable.assert_not_called()
    spawn_and_combat = (GateKind.SPAWN_LIVE, GateKind.SPAWN_KNOWN, GateKind.WINNABLE)
    assert all(not g.satisfied for r in routes if r.kind is SourceKind.DROP for g in r.gates
               if g.kind in spawn_and_combat)


def test_recycle_skips_holdings_that_cannot_be_recycled(world: tuple[WorldState, GameData]) -> None:
    """A held consumer of the item that is not equippable has no RecycleAction
    in existence, so it is no route at all rather than a gated one."""
    state, gd = world
    item, consumer = next((mat, code) for code, recipe in sorted(gd.crafting_recipes.items())
                          for mat in recipe
                          if (s := gd.item_stats(code)) is not None and s.type_ == "resource")
    held = replace(state, inventory={**state.inventory, consumer: 1})
    routes = ObtainModel(held, gd, _ctx(), NOW).routes(item)
    assert not [r for r in routes if r.kind is SourceKind.RECYCLE and r.via == consumer]


def test_a_recipe_whose_item_names_no_crafting_skill_is_no_craft_route(
        world: tuple[WorldState, GameData]) -> None:
    """No crafting skill means no workshop to craft at, so no CraftAction
    exists; `obtain_sources` skips it too."""
    state, gd = world
    stats = replace(gd.item_stats("copper_bar"), crafting_skill="")
    with patch.object(GameData, "item_stats", return_value=stats):
        routes = ObtainModel(state, gd, _ctx(), NOW).routes("copper_bar")
    assert not [r for r in routes if r.kind is SourceKind.CRAFT]


class TestFeasible:
    """`ObtainModel.feasible` over hand-made route tables, so each case names
    exactly what it exercises. The quantity walk itself is pinned by the Lean
    differential; these cover the model's wiring: what counts as on hand, the
    input closure, gold as an input, and the blockers it reports."""

    GATHER_GATE = Gate(GateKind.GATHER_SKILL, "mining", False, 10)

    def _model(self, world: tuple[WorldState, GameData], table: dict[str, tuple[Route, ...]],
               **state_changes: object) -> ObtainModel:
        state, gd = world
        model = ObtainModel(replace(state, **state_changes), gd, _ctx(), NOW)
        model._routes = dict(table)
        for code in ("ore", "bar", "ring", "ghost", "loop_a", "loop_b", GOLD_CODE):
            model._routes.setdefault(code, ())
        return model

    def _craft(self, item: str, **inputs: int) -> Route:
        return Route(item, SourceKind.CRAFT, item, 1, 10**9, (), inputs=inputs)

    def test_a_held_item_is_feasible_up_to_the_count_held(
            self, world: tuple[WorldState, GameData]) -> None:
        model = self._model(world, {}, inventory={"ghost": 2}, equipment={}, gold=0)
        assert model.feasible("ghost", 2, LEGACY).ok and not model.feasible("ghost", 3, LEGACY).ok

    def test_pocket_gold_is_on_hand_and_worn_gear_is_not(
            self, world: tuple[WorldState, GameData]) -> None:
        model = self._model(world, {}, inventory={}, equipment={"weapon_slot": "ghost"}, gold=5)
        assert not model.feasible("ghost", 1, LEGACY).ok
        assert model.feasible(GOLD_CODE, 5, LEGACY).ok and not model.feasible(GOLD_CODE, 6, LEGACY).ok

    def test_a_chain_of_unbounded_routes_is_feasible_in_any_amount(
            self, world: tuple[WorldState, GameData]) -> None:
        table = {"ore": (Route("ore", SourceKind.GATHER, "rocks", 1, 10**9, ()),),
                 "bar": (self._craft("bar", ore=10),),
                 "ring": (self._craft("ring", bar=6),)}
        model = self._model(world, table, inventory={}, equipment={}, gold=0)
        assert model.feasible("ring", 50, LEGACY) == Feasibility(ok=True)

    def test_banked_stock_bounds_the_amount(self, world: tuple[WorldState, GameData]) -> None:
        """Six banked bars make one ring (six per craft) and not two."""
        table = {"ring": (self._craft("ring", bar=6),),
                 "bar": (Route("bar", SourceKind.WITHDRAW, "bar", 1, 6, ()),)}
        model = self._model(world, table, inventory={}, equipment={}, gold=0)
        assert model.feasible("ring", 1, LEGACY).ok
        assert model.feasible("ring", 2, LEGACY) == Feasibility(ok=False, missing_inputs=("bar",))

    def test_a_gold_price_is_an_input(self, world: tuple[WorldState, GameData]) -> None:
        """A vendor is a route only as far as the pocket pays for it."""
        table = {"ore": (Route("ore", SourceKind.BUY, "smith", 1, 10**9, (),
                               inputs={GOLD_CODE: 30}),)}
        model = self._model(world, table, inventory={}, equipment={}, gold=60)
        assert model.feasible("ore", 2, LEGACY).ok
        assert model.feasible("ore", 3, LEGACY) == Feasibility(ok=False, missing_inputs=(GOLD_CODE,))

    def test_a_route_delivers_no_more_than_its_capacity(
            self, world: tuple[WorldState, GameData]) -> None:
        table = {"ore": (Route("ore", SourceKind.GE_FILL, "order", 1, 4, (),
                               inputs={GOLD_CODE: 1}),)}
        model = self._model(world, table, inventory={}, equipment={}, gold=100)
        assert model.feasible("ore", 4, LEGACY).ok and not model.feasible("ore", 5, LEGACY).ok

    def test_an_unmet_gate_is_named(self, world: tuple[WorldState, GameData]) -> None:
        """When the gather skill is enforced and unmet, it is the reason
        reported; a policy ignoring it finds the gather."""
        table = {"ore": (Route("ore", SourceKind.GATHER, "rocks", 1, 10**9, (self.GATHER_GATE,)),)}
        model = self._model(world, table, inventory={}, equipment={}, gold=0)
        assert model.feasible("ore", 1, replace(LEGACY, gather_skill_gate=False)).ok
        assert model.feasible("ore", 1, OPEN) == Feasibility(ok=False, blocking_gates=(self.GATHER_GATE,))

    def test_an_unobtainable_input_is_named(self, world: tuple[WorldState, GameData]) -> None:
        table = {"ring": (self._craft("ring", bar=6, ghost=1),),
                 "bar": (Route("bar", SourceKind.WITHDRAW, "bar", 1, 6, ()),)}
        model = self._model(world, table, inventory={}, equipment={}, gold=0)
        assert model.feasible("ring", 1, LEGACY) == Feasibility(ok=False, missing_inputs=("ghost",))

    def test_a_cycle_is_not_its_own_way_in(self, world: tuple[WorldState, GameData]) -> None:
        table = {"loop_a": (self._craft("loop_a", loop_b=1),),
                 "loop_b": (self._craft("loop_b", loop_a=1),)}
        model = self._model(world, table, inventory={}, equipment={}, gold=0)
        assert not model.feasible("loop_a", 1, LEGACY).ok
        assert self._model(world, table, inventory={"loop_b": 1}, equipment={},
                           gold=0).feasible("loop_a", 1, LEGACY).ok

    def test_an_item_with_no_route_and_no_holding_has_no_reason_to_give(
            self, world: tuple[WorldState, GameData]) -> None:
        model = self._model(world, {}, inventory={}, equipment={}, gold=0)
        assert model.feasible("ghost", 1, LEGACY) == Feasibility(ok=False)


def test_feasible_runs_over_the_real_catalogue(world: tuple[WorldState, GameData]) -> None:
    """Every item of real game data gets an answer, and every feasible verdict
    is backed by stock or a ready route (a smoke check that the closure walk
    terminates on real recipes)."""
    state, gd = world
    model = ObtainModel(state, gd, _ctx(), NOW)
    verdicts = {item: model.feasible(item, 1, LEGACY) for item in census_items(gd)}
    assert any(v.ok for v in verdicts.values()) and any(not v.ok for v in verdicts.values())
    assert all(model.on_hand(item, LEGACY) or model.ready(item, LEGACY)
               for item, v in verdicts.items() if v.ok)


def test_drop_routes_evaluate_winnability_only_for_a_monster_that_spawns(
        world: tuple[WorldState, GameData]) -> None:
    """A layered monster in a reachable region spawns (`SPAWN_KNOWN`) without a
    live tile, so its winnability IS asked; one that spawns nowhere is not."""
    state, gd = world
    item = next(i for i in sorted(gd.all_item_stats) if gd.monsters_dropping(i))
    monster = gd.monsters_dropping(item)[0][0]
    with (patch.object(GameData, "all_monster_locations", new={}),
          patch.object(GameData, "monster_spawn_known", side_effect=lambda code: code == monster),
          patch("artifactsmmo_cli.ai.obtain_model.drop_routes.is_winnable", return_value=True) as winnable):
        routes = drop_routes(item, state, gd)
    assert [call.args[2] for call in winnable.call_args_list] == [monster]
    gates = {g.kind: g.satisfied for g in routes[0].gates}
    assert gates[GateKind.SPAWN_KNOWN] and gates[GateKind.WINNABLE] and not gates[GateKind.SPAWN_LIVE]


class TestOnHand:
    """What `on_hand` counts: the bag, reachable bank copies and licensed
    recycles, never a purchase or a worn copy."""

    def test_the_bag_and_the_bank_are_on_hand(self, world: tuple[WorldState, GameData]) -> None:
        state, gd = world
        model = ObtainModel(replace(state, inventory={"hard_leather": 2},
                                    bank_items={"hard_leather": 3}), gd, _ctx(), NOW)
        assert model.on_hand("hard_leather", OPEN) == 5
        assert model.feasible("hard_leather", 5, OPEN).ok
        assert not model.feasible("hard_leather", 6, OPEN).ok

    def test_a_locked_bank_is_not_on_hand(self, world: tuple[WorldState, GameData]) -> None:
        state, gd = world
        model = ObtainModel(replace(state, bank_items={"hard_leather": 3}), gd,
                            _ctx(bank_accessible=False), NOW)
        assert model.on_hand("hard_leather", OPEN) == state.inventory.get("hard_leather", 0)

    def test_worn_gear_and_a_ge_order_are_not_on_hand(
            self, world: tuple[WorldState, GameData]) -> None:
        """A worn copy would have to be unequipped, and a GE fill is a purchase."""
        state, gd = world
        worn = next(code for code in state.equipment.values() if code)
        model = ObtainModel(replace(state, inventory={}, bank_items={}), gd, _ctx(), NOW)
        assert any(r.kind is SourceKind.GE_FILL for r in model.ready(worn, OPEN)), \
            "vacuous: no GE order for the worn item"
        assert model.on_hand(worn, OPEN) == 0

    def test_a_ge_order_costs_its_price_in_gold(self, world: tuple[WorldState, GameData]) -> None:
        state, gd = world
        worn = next(code for code in state.equipment.values() if code)
        [order] = [r for r in ObtainModel(state, gd, _ctx(), NOW).routes(worn)
                   if r.kind is SourceKind.GE_FILL]
        assert order.inputs == {GOLD_CODE: gd.ge_best_sell_order(worn)[1]}


def test_the_task_board_is_a_route_to_what_it_pays(
        world: tuple[WorldState, GameData]) -> None:
    """D-N: `tasks_coin` has a route, one task loop per application, with no
    inputs and no capacity limit, so any amount can be earned."""
    state, gd = world
    model = ObtainModel(replace(state, inventory={}, bank_items={}), gd, _ctx(), NOW)
    [route] = [r for r in model.routes(TASKS_COIN_CODE) if r.kind is SourceKind.TASK_REWARD]
    assert route.capacity == UNBOUNDED_CAPACITY and not route.inputs
    assert not [r for r in model.routes("copper_ore") if r.kind is SourceKind.TASK_REWARD]
    assert model.feasible(TASKS_COIN_CODE, 50, OPEN).ok
    assert not model.feasible(TASKS_COIN_CODE, 50, LEGACY).ok



def test_mints_is_capability_not_stock(world: tuple[WorldState, GameData]) -> None:
    """A craft, a gather, a drop, a vendor and the task board make new copies
    whatever their gates say today; a banked copy, a GE order and a sale only
    move copies that exist."""
    state, gd = world
    model = ObtainModel(replace(state, level=1, skills={}), gd, _ctx(), NOW)
    assert model.mints("copper_bar") and model.mints("copper_ore") and model.mints(TASKS_COIN_CODE)
    dropped = next(i for i in sorted(gd.all_item_stats) if gd.monsters_dropping(i)
                   and not gd.crafting_recipe(i) and not gd.npc_purchases(i)
                   and i not in gd.gatherable_drop_items())
    assert model.mints(dropped)
    owned_only = ObtainModel(replace(state, bank_items={"novice_guide": 1}), gd, _ctx(), NOW)
    assert owned_only.routes("novice_guide") and not owned_only.mints("novice_guide")
    # Gold is minted by fighting; with no monster paying any, a sale alone is
    # stock, not a mint.
    assert model.mints(GOLD_CODE)
    with patch.object(GameData, "monster_max_gold", return_value=0):
        assert not ObtainModel(state, gd, _ctx(), NOW).mints(GOLD_CODE)


def test_every_monster_that_pays_gold_is_a_gold_route(world: tuple[WorldState, GameData]) -> None:
    """Gold is earned by winning fights: one GOLD_DROP route per paying
    monster, yielding the expected (min + max) // 2 per win, with the same
    fight gates as an item drop. A monster that pays nothing has no route."""
    state, gd = world
    routes = [r for r in ObtainModel(state, gd, _ctx(), NOW).routes(GOLD_CODE)
              if r.kind is SourceKind.GOLD_DROP]
    paying = [m for m in gd.monsters.levels if gd.monster_max_gold(m) > 0]
    assert [r.via for r in routes] == paying and len(paying) < len(gd.monsters.levels)
    for r in routes:
        assert r.yield_per == max(1, (gd.monster_min_gold(r.via) + gd.monster_max_gold(r.via)) // 2)
        assert {g.kind for g in r.gates} == {GateKind.SPAWN_LIVE, GateKind.SPAWN_KNOWN,
                                             GateKind.WINNABLE, GateKind.XP_POSITIVE}
    # A geared character can earn any amount of gold by fighting; the world
    # fixture is a zero-stat state (no fight winnable), so it cannot.
    geared = scenario_state(replace(SCENARIOS["l20_band_entry"], derive_combat_stats=True), gd)
    assert ObtainModel(replace(geared, gold=0), gd, _ctx(), NOW).feasible(GOLD_CODE, 10**6, OPEN).ok
    assert not ObtainModel(replace(state, gold=0), gd, _ctx(), NOW).feasible(GOLD_CODE, 1, OPEN).ok


class TestGatedBy:
    """`gated_by`: routes that ONE kind of gate alone keeps closed."""

    def _model(self, world: tuple[WorldState, GameData], *routes: Route) -> ObtainModel:
        state, gd = world
        model = ObtainModel(state, gd, _ctx(), NOW)
        model._routes = {"x": routes}
        return model

    def test_a_route_blocked_only_by_that_gate_is_named(self, world: tuple[WorldState, GameData]) -> None:
        skill = Gate(GateKind.CRAFT_SKILL, "mining", False, 10)
        craft = Route("x", SourceKind.CRAFT, "x", 1, 10**9, (skill, Gate(GateKind.WORKSHOP_KNOWN, "mining", True)))
        assert self._model(world, craft).gated_by("x", LEGACY, GateKind.CRAFT_SKILL) == (craft,)

    def test_a_second_unmet_gate_makes_it_a_wall(self, world: tuple[WorldState, GameData]) -> None:
        craft = Route("x", SourceKind.CRAFT, "x", 1, 10**9, (
            Gate(GateKind.CRAFT_SKILL, "mining", False, 10), Gate(GateKind.WORKSHOP_KNOWN, "mining", False)))
        assert self._model(world, craft).gated_by("x", LEGACY, GateKind.CRAFT_SKILL) == ()

    def test_a_ready_route_or_an_unenforced_gate_is_not_gated(self, world: tuple[WorldState, GameData]) -> None:
        ready = Route("x", SourceKind.CRAFT, "x", 1, 10**9, (Gate(GateKind.CRAFT_SKILL, "mining", True, 1),))
        grey = Route("x", SourceKind.DROP, "m", 1, 10**9, (Gate(GateKind.XP_POSITIVE, "m", False),))
        model = self._model(world, ready, grey)
        assert model.gated_by("x", LEGACY, GateKind.CRAFT_SKILL) == ()
        assert model.gated_by("x", LEGACY, GateKind.XP_POSITIVE) == ()  # LEGACY allows grey

    def test_a_route_the_policy_does_not_offer_is_not_gated(self, world: tuple[WorldState, GameData]) -> None:
        fill = Route("x", SourceKind.GE_FILL, "o", 1, 5, (Gate(GateKind.GE_LOCATED, "ge", False),))
        model = self._model(world, fill)
        assert model.gated_by("x", LEGACY, GateKind.GE_LOCATED) == (fill,)
        assert model.gated_by("x", replace(LEGACY, ge_routes=False), GateKind.GE_LOCATED) == ()

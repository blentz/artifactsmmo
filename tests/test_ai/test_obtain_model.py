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
from artifactsmmo_cli.ai.obtain_model.route import Route
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.world_state import GOLD_CODE, WorldState

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"
NOW = datetime(2026, 9, 27, tzinfo=UTC)
OPEN = Policy(all_gather_routes=True, gather_skill_gate=True, event_vendors=True,
              drop_spawn_known=True, allow_grey=False)


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
    assert [g.kind for g in route.gates] == [GateKind.SPAWN_LIVE]


class TestPolicy:
    def _route(self, kind: SourceKind, *gates: Gate, primary: bool = True) -> Route:
        return Route("x", kind, "v", 1, 1, gates, primary=primary)

    def test_the_gather_skill_gate_counts_only_when_enforced(self) -> None:
        route = self._route(SourceKind.GATHER, Gate(GateKind.GATHER_SKILL, "mining", False, 10))
        assert LEGACY.ready(route) and not OPEN.ready(route)

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

    def test_a_drop_enforces_one_spawn_predicate_chosen_by_the_policy(self) -> None:
        """D-D: LEGACY asks for a live tile, OPEN for a routable spawn."""
        layered_only = self._route(SourceKind.DROP, Gate(GateKind.SPAWN_LIVE, "m", False),
                                   Gate(GateKind.SPAWN_KNOWN, "m", True))
        assert not LEGACY.ready(layered_only) and OPEN.ready(layered_only)
        live_only = self._route(SourceKind.DROP, Gate(GateKind.SPAWN_LIVE, "m", True),
                                Gate(GateKind.SPAWN_KNOWN, "m", False))
        assert LEGACY.ready(live_only) and not OPEN.ready(live_only)

    def test_a_grey_dropper_counts_only_when_grey_is_allowed(self) -> None:
        grey = self._route(SourceKind.DROP, Gate(GateKind.XP_POSITIVE, "m", False))
        assert LEGACY.ready(grey) and not OPEN.ready(grey)

    def test_spawn_live_still_gates_a_gather_route_under_every_policy(self) -> None:
        dead = self._route(SourceKind.GATHER, Gate(GateKind.SPAWN_LIVE, "rocks", False))
        assert not LEGACY.ready(dead) and not OPEN.ready(dead)

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
        routes = model.routes(GOLD_CODE)
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
    exactly what it exercises. The fixpoint itself is pinned by the Lean
    differential; these cover the model's wiring: holdings, the input closure,
    and the blockers it reports."""

    GATHER_GATE = Gate(GateKind.GATHER_SKILL, "mining", False, 10)

    def _model(self, world: tuple[WorldState, GameData], table: dict[str, tuple[Route, ...]],
               **state_changes: object) -> ObtainModel:
        state, gd = world
        model = ObtainModel(replace(state, **state_changes), gd, _ctx(), NOW)
        model._routes = dict(table)
        for code in ("ore", "bar", "ring", "ghost", "loop_a", "loop_b"):
            model._routes.setdefault(code, ())
        return model

    def _craft(self, item: str, **inputs: int) -> Route:
        return Route(item, SourceKind.CRAFT, item, 1, 10**9, (), inputs=inputs)

    def test_a_held_item_is_feasible_with_no_route(self, world: tuple[WorldState, GameData]) -> None:
        model = self._model(world, {}, inventory={"ghost": 1}, equipment={}, gold=0)
        assert model.feasible("ghost", LEGACY).ok

    def test_worn_gear_and_pocket_gold_count_as_held(self, world: tuple[WorldState, GameData]) -> None:
        model = self._model(world, {}, inventory={}, equipment={"weapon_slot": "ghost"}, gold=5)
        assert model.feasible("ghost", LEGACY).ok
        assert model.feasible(GOLD_CODE, LEGACY).ok

    def test_a_chain_of_ready_routes_is_feasible(self, world: tuple[WorldState, GameData]) -> None:
        table = {"ore": (Route("ore", SourceKind.GATHER, "rocks", 1, 10**9, ()),),
                 "bar": (self._craft("bar", ore=10),),
                 "ring": (self._craft("ring", bar=6),)}
        model = self._model(world, table, inventory={}, equipment={}, gold=0)
        assert model.feasible("ring", LEGACY) == Feasibility(ok=True)

    def test_an_unmet_gate_is_named(self, world: tuple[WorldState, GameData]) -> None:
        """The gather skill is ignored under LEGACY and enforced under OPEN; when
        enforced and unmet, it is the reason reported."""
        table = {"ore": (Route("ore", SourceKind.GATHER, "rocks", 1, 10**9, (self.GATHER_GATE,)),)}
        model = self._model(world, table, inventory={}, equipment={}, gold=0)
        assert model.feasible("ore", LEGACY).ok
        assert model.feasible("ore", OPEN) == Feasibility(ok=False, blocking_gates=(self.GATHER_GATE,))

    def test_an_unobtainable_input_is_named(self, world: tuple[WorldState, GameData]) -> None:
        table = {"ring": (self._craft("ring", bar=6, ghost=1),),
                 "bar": (Route("bar", SourceKind.WITHDRAW, "bar", 1, 6, ()),)}
        model = self._model(world, table, inventory={}, equipment={}, gold=0)
        assert model.feasible("ring", LEGACY) == Feasibility(ok=False, missing_inputs=("ghost",))

    def test_a_cycle_is_not_its_own_way_in(self, world: tuple[WorldState, GameData]) -> None:
        table = {"loop_a": (self._craft("loop_a", loop_b=1),),
                 "loop_b": (self._craft("loop_b", loop_a=1),)}
        model = self._model(world, table, inventory={}, equipment={}, gold=0)
        assert not model.feasible("loop_a", LEGACY).ok
        assert self._model(world, table, inventory={"loop_b": 1}, equipment={},
                           gold=0).feasible("loop_a", LEGACY).ok

    def test_an_item_with_no_route_and_no_holding_has_no_reason_to_give(
            self, world: tuple[WorldState, GameData]) -> None:
        model = self._model(world, {}, inventory={}, equipment={}, gold=0)
        assert model.feasible("ghost", LEGACY) == Feasibility(ok=False)


def test_feasible_runs_over_the_real_catalogue(world: tuple[WorldState, GameData]) -> None:
    """Every item of real game data gets an answer, and every feasible verdict
    is backed by a holding or a ready route (a smoke check that the closure
    walk terminates on real recipes)."""
    state, gd = world
    model = ObtainModel(state, gd, _ctx(), NOW)
    verdicts = {item: model.feasible(item, LEGACY) for item in census_items(gd)}
    assert any(v.ok for v in verdicts.values()) and any(not v.ok for v in verdicts.values())
    held = model._held()
    assert all(item in held or model.ready(item, LEGACY) for item, v in verdicts.items() if v.ok)


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

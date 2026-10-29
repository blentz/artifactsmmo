"""Task 14e (finding M-3): a key door is a route through its key.

Ruling T14a-E made `region_edges.reachable_regions_now` the one reachability
authority: content past a door whose key or fee is not held is unreached, so
its route is not ready. The authority stays strict; the door is named on the
unmet SPAWN_KNOWN gate (`Gate.doors`, `region_edges.doors_to`), the walk opens
it by obtaining the key (`ObtainModel.walk_graph`), the executor plans the key
first (`craft_plan_gen._open_door`), and the pricer charges the key's own
price plus the crossing as the route's unlock (`acquisition_cost._door_options`).
"""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from artifactsmmo_api_client.models.access_schema import AccessSchema
from artifactsmmo_api_client.models.condition_schema import ConditionSchema
from artifactsmmo_api_client.models.interaction_schema import InteractionSchema
from artifactsmmo_api_client.models.map_access_type import MapAccessType
from artifactsmmo_api_client.models.map_content_schema import MapContentSchema
from artifactsmmo_api_client.models.map_content_type import MapContentType
from artifactsmmo_api_client.models.map_layer import MapLayer
from artifactsmmo_api_client.models.map_schema import MapSchema
from artifactsmmo_api_client.models.transition_schema import TransitionSchema

from artifactsmmo_cli.ai import acquisition_cost, region_edges
from artifactsmmo_cli.ai.acquisition_cost import (
    CROSSING_ACTIONS,
    acquisition_actions,
    door_route,
    route_options,
)
from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.transition import MapTransitionAction
from artifactsmmo_cli.ai.combat_deficit import CombatDeficit, DeficitStep
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.decompose_core import OpenGate
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.obtain_model import drop_routes as drop_routes_module
from artifactsmmo_cli.ai.obtain_model.gate import Gate, GateKind
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import DECOMPOSE_POLICY, PIECE_POLICY
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.region_edges import door_reaches, doors_to, reachable_regions_now
from artifactsmmo_cli.ai.scenario import SCENARIOS, derived_scenario_state
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.world_state import GOLD_CODE, WorldState
from artifactsmmo_cli.audit import craft_completeness
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT, make_state
from tests.test_ai.shared_world import shared_world

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")

LICH_DOOR = (("lich_tomb_key", 1),)
"""The lich tomb's door (overworld (9,7) -> `underground:9,7`): one consumed
`lich_tomb_key`, which skeletons, vampires and death knights drop."""


def _tile(map_id: int, x: int, y: int, layer: str, content: MapContentSchema | None = None,
          transition: TransitionSchema | None = None) -> MapSchema:
    return MapSchema(map_id=map_id, name="t", skin="s", x=x, y=y, layer=MapLayer(layer),
                     access=AccessSchema(type_=MapAccessType.STANDARD),
                     interactions=InteractionSchema(content=content, transition=transition))


def _door_world(monkeypatch: pytest.MonkeyPatch, key_outside: bool) -> GameData:
    """An overworld, and an interior past a door that asks a held `vault_key`.
    The interior's `warden` drops `vault_key` and `loot`; with `key_outside`
    the overworld `smith` drops the key as well. Every fight is winnable."""
    world = GameData()
    tiles = [
        _tile(1, 0, 0, "overworld"),
        _tile(2, 1, 0, "overworld", transition=TransitionSchema(
            map_id=3, x=3, y=0, layer="interior",
            conditions=[ConditionSchema(code="vault_key", operator="has_item", value=1)])),
        _tile(3, 3, 0, "interior",
              content=MapContentSchema(type_=MapContentType.MONSTER, code="warden")),
    ]
    if key_outside:
        tiles.append(_tile(4, 0, 1, "overworld",
                           content=MapContentSchema(type_=MapContentType.MONSTER, code="smith")))
    world._build_maps(tiles)
    droppers = {"loot": [("warden", 1, 1, 1)],
                "vault_key": [("warden", 1, 1, 1)] + ([("smith", 1, 1, 1)] if key_outside else [])}
    monkeypatch.setattr(world, "monsters_dropping", lambda item: droppers.get(item, []))
    monkeypatch.setattr(world, "xp_per_kill", lambda monster, level, wisdom=0: 1)
    monkeypatch.setattr(drop_routes_module, "drop_fight_winnable", lambda rested, gd, monster: True)
    return world


def _two_door_world(monkeypatch: pytest.MonkeyPatch, vault_from_warden: bool = False) -> GameData:
    """Two doors into the warden's interior: the first (tile order) asks a
    held `vault_key` nothing drops, the second a held `spare_key` the
    overworld `smith` drops. With `vault_from_warden` the warden drops the
    vault key."""
    world = GameData()
    world._build_maps([
        _tile(1, 0, 0, "overworld"),
        _tile(2, 0, 1, "overworld", transition=TransitionSchema(
            map_id=4, x=3, y=0, layer="interior",
            conditions=[ConditionSchema(code="vault_key", operator="has_item", value=1)])),
        _tile(3, 1, 0, "overworld", transition=TransitionSchema(
            map_id=4, x=3, y=0, layer="interior",
            conditions=[ConditionSchema(code="spare_key", operator="has_item", value=1)])),
        _tile(4, 3, 0, "interior",
              content=MapContentSchema(type_=MapContentType.MONSTER, code="warden")),
        _tile(5, 1, 1, "overworld",
              content=MapContentSchema(type_=MapContentType.MONSTER, code="smith")),
    ])
    droppers = {"loot": [("warden", 1, 1, 1)], "spare_key": [("smith", 1, 1, 1)],
                "vault_key": [("warden", 1, 1, 1)] if vault_from_warden else []}
    monkeypatch.setattr(world, "monsters_dropping", lambda item: droppers.get(item, []))
    monkeypatch.setattr(world, "xp_per_kill", lambda monster, level, wisdom=0: 1)
    monkeypatch.setattr(drop_routes_module, "drop_fight_winnable", lambda rested, gd, monster: True)
    return world


def _model(state: WorldState, world: GameData) -> ObtainModel:
    return ObtainModel(state, world, TIMED_NO_PROFILE_CONTEXT, datetime.now(UTC))


def _seeded(name: str) -> tuple[WorldState, GameData, GamePlayer]:
    sc = SCENARIOS[name]
    world = shared_world(BUNDLE, with_ge_orders=sc.ge_market,
                         completed_achievements=frozenset(sc.unlocked_achievements))
    world.active_event_codes = set(sc.active_events)
    world.active_raid_codes = {code for code, _boss in sc.raids}
    player = GamePlayer(character=sc.name, history=None)
    player.seed_offline(derived_scenario_state(sc, world), world)
    assert player.state is not None
    return player.state, world, player


# --- the authority names the door -------------------------------------------

def test_a_door_s_shortfall_is_what_the_state_lacks() -> None:
    """`MapTransitionAction.shortfall`: the fee past the pocket, a consumed key
    past the bag, a `has_item` key past the bag and the worn slots; None for an
    operator the model refuses."""
    edge = MapTransitionAction(conditions=(("gold", "cost", 100), ("tomb_key", "cost", 2),
                                           ("cloak", "has_item", 1)))
    assert edge.shortfall(make_state(gold=30)) == {GOLD_CODE: 70, "tomb_key": 2, "cloak": 1}
    held = make_state(gold=100, inventory={"tomb_key": 1}, equipment={"body_armor_slot": "cloak"})
    assert edge.shortfall(held) == {"tomb_key": 1}
    assert edge.shortfall(make_state(gold=200, inventory={"tomb_key": 2, "cloak": 1})) == {}
    unmodeled = MapTransitionAction(conditions=(("deep_delver", "achievement_unlocked", 1),))
    assert unmodeled.shortfall(make_state()) is None


def test_a_door_past_the_reach_names_its_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The warden is past the vault door: unreached, and the door is named by
    the shortfall that reaches it. Holding the key, it is reached and no door
    is left; an edge whose portal the walk cannot reach is no door."""
    world = _door_world(monkeypatch, key_outside=True)
    poor = make_state(x=0, y=0)
    assert "interior:3,0" not in reachable_regions_now(poor, world)
    assert door_reaches(poor, world) == (((("vault_key", 1),), frozenset({"interior:3,0"})),)
    assert doors_to("warden", [], poor, world) == ((("vault_key", 1),),)
    assert doors_to("smith", [(0, 1)], poor, world) == ()
    holding = replace(poor, inventory={"vault_key": 1})
    assert door_reaches(holding, world) == ()
    inside = make_state(x=3, y=0, layer="interior")
    assert door_reaches(inside, world) == ()


def test_a_door_that_reaches_nothing_new_is_no_door(monkeypatch: pytest.MonkeyPatch) -> None:
    """A second door into a region the walk already reaches opens nothing."""
    world = GameData()
    world._build_maps([
        _tile(1, 0, 0, "overworld"),
        _tile(2, 1, 0, "overworld", transition=TransitionSchema(
            map_id=1, x=0, y=0, layer="overworld",
            conditions=[ConditionSchema(code="gold", operator="cost", value=50)])),
    ])
    assert door_reaches(make_state(gold=0), world) == ()


def test_the_door_memo_is_scoped_and_keyed_as_the_reach_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """`door_reaches` is remembered per catalogue and per `_reach_key`."""
    world = _door_world(monkeypatch, key_outside=True)
    state = make_state(x=0, y=0)
    region_edges._DOORS.clear()
    first = door_reaches(state, world)
    assert door_reaches(state, world) is first
    assert list(region_edges._DOORS.cache_for(world)) == [region_edges._reach_key(state, world)]


def test_a_fight_past_a_door_carries_the_door_and_its_winnability(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The warden's DROP route: SPAWN_KNOWN unmet with the door named, and
    WINNABLE asked (it spawns past a door), so the door alone keeps it shut."""
    world = _door_world(monkeypatch, key_outside=True)
    (route,) = _model(make_state(x=0, y=0), world).routes("loot")
    known = next(g for g in route.gates if g.kind is GateKind.SPAWN_KNOWN)
    assert (known.satisfied, known.doors) == (False, ((("vault_key", 1),),))
    assert next(g.satisfied for g in route.gates if g.kind is GateKind.WINNABLE)
    assert _model(make_state(x=0, y=0), world).gated_by("loot", DECOMPOSE_POLICY,
                                                        GateKind.SPAWN_KNOWN) == (route,)


# --- the walk routes through the key ----------------------------------------

def test_the_walk_routes_through_an_obtainable_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The smith drops the key outside: `loot` is feasible, and the walk's
    first step opens the door (the gate narrowed to the door it opens)."""
    world = _door_world(monkeypatch, key_outside=True)
    model = _model(make_state(x=0, y=0), world)
    assert model.feasible("loot", 1, DECOMPOSE_POLICY)
    step = model.walk("loot", 1, DECOMPOSE_POLICY).plan[0]
    assert isinstance(step, OpenGate) and isinstance(step.gate, Gate)
    gate = step.gate
    assert (gate.kind, gate.doors) == (GateKind.SPAWN_KNOWN, ((("vault_key", 1),),))
    assert model.door_open((("vault_key", 1),), DECOMPOSE_POLICY)


def test_the_walk_opens_the_door_whose_key_it_can_obtain(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Two doors, the first walled (nothing yields its key): the gate the walk
    carries is narrowed to the second, the door the executor then opens."""
    world = _two_door_world(monkeypatch)
    model = _model(make_state(x=0, y=0), world)
    (route,) = model.routes("loot")
    assert next(g.doors for g in route.gates if g.kind is GateKind.SPAWN_KNOWN) == (
        (("vault_key", 1),), (("spare_key", 1),))
    step = model.walk("loot", 1, DECOMPOSE_POLICY).plan[0]
    assert isinstance(step, OpenGate) and isinstance(step.gate, Gate)
    gate = step.gate
    assert gate.doors == ((("spare_key", 1),),)


def test_a_key_past_another_door_is_walked_through_that_door(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The vault key drops only past the doors, one of which is the spare
    key's: the vault door opens through the spare key (recursion), and only
    the vault door is closed to its own key's walk."""
    world = _two_door_world(monkeypatch, vault_from_warden=True)
    model = _model(make_state(x=0, y=0), world)
    assert model.feasible("vault_key", 1, DECOMPOSE_POLICY)
    assert model.door_open((("vault_key", 1),), DECOMPOSE_POLICY)


def test_a_gather_past_a_door_names_the_door() -> None:
    """`enchanted_mushroom` grows only past the 5000-gold door: its gather's
    SPAWN_KNOWN gate names the fee the pocket lacks."""
    state, world, player = _seeded("l48_band_adequate")
    model = ObtainModel(state, world, player._selection_context(), datetime.now(UTC))
    (route,) = [r for r in model.routes("enchanted_mushroom") if r.kind is SourceKind.GATHER]
    gate = next(g for g in route.gates if g.kind is GateKind.SPAWN_KNOWN)
    assert (gate.satisfied, gate.doors) == (False, (((GOLD_CODE, 5000 - state.gold),),))


def test_a_key_behind_its_own_door_is_a_wall(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only the warden, past the vault door, drops the vault key: the key
    cannot open its own door, so `loot` is a wall for the walk and for the
    pricer, and the door is still named on the gate."""
    world = _door_world(monkeypatch, key_outside=False)
    state = make_state(x=0, y=0)
    model = _model(state, world)
    assert not model.feasible("loot", 1, DECOMPOSE_POLICY)
    assert not model.feasible("vault_key", 1, DECOMPOSE_POLICY)
    assert not model.door_open((("vault_key", 1),), DECOMPOSE_POLICY)
    (route,) = model.routes("loot")
    assert next(g.doors for g in route.gates if g.kind is GateKind.SPAWN_KNOWN)
    assert route_options("loot", state, world, TIMED_NO_PROFILE_CONTEXT, policy=PIECE_POLICY) == []
    assert acquisition_actions("loot", 1, state, world, TIMED_NO_PROFILE_CONTEXT, equip=False,
                               policy=PIECE_POLICY) >= UNOBTAINABLE_PER_UNIT


def test_an_unopenable_second_gate_keeps_the_route_shut(monkeypatch: pytest.MonkeyPatch) -> None:
    """A door opens the SPAWN_KNOWN gate only: a route also refused for grey
    stays out of the walk however obtainable the key is."""
    world = _door_world(monkeypatch, key_outside=True)
    monkeypatch.setattr(world, "xp_per_kill", lambda monster, level, wisdom=0: 0)
    model = _model(make_state(x=0, y=0), world)
    assert not model.feasible("loot", 1, DECOMPOSE_POLICY)


# --- the price is the key's, plus the crossing, plus the route ---------------

def test_a_monster_behind_a_key_door_is_priced_through_the_key(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """`life_crystal_shard` drops only from the lich, past the lich tomb's
    door. With the key in the bag the farm is a ready route; without it, the
    price is that farm's plus the key's own price plus the crossing, paid once
    (the route's unlock)."""
    state, world, _player = _seeded("l48_band_adequate")
    monkeypatch.setattr(drop_routes_module, "drop_fight_winnable", lambda rested, gd, monster: True)
    ctx = TIMED_NO_PROFILE_CONTEXT
    assert state.inventory.get("lich_tomb_key", 0) == 0
    assert LICH_DOOR in [door for door, _beyond in door_reaches(state, world)]
    holding = replace(state, inventory={**state.inventory, "lich_tomb_key": 1})

    def price(at: WorldState, item: str, qty: int, **kw: object) -> int:
        return acquisition_actions(item, qty, at, world, ctx, equip=False,
                                   policy=PIECE_POLICY, **kw)  # type: ignore[arg-type]

    rest = price(holding, "life_crystal_shard", 1)
    key = price(state, "lich_tomb_key", 1, opening=frozenset({LICH_DOOR}))
    assert rest < UNOBTAINABLE_PER_UNIT and key < UNOBTAINABLE_PER_UNIT
    assert price(state, "life_crystal_shard", 1) == rest + key + CROSSING_ACTIONS
    (option,) = route_options("life_crystal_shard", state, world, ctx, policy=PIECE_POLICY)
    assert (option.kind, option.venue) == (SourceKind.DROP.value, "lich")
    assert (option.unlock, option.unlock_actions) == ("door:lich_tomb_keyx1", key + CROSSING_ACTIONS)


def test_the_cheapest_door_prices_the_route(monkeypatch: pytest.MonkeyPatch) -> None:
    """Of two doors past which the content stands, the route takes the one
    whose key prices cheaper; a door already being priced further up is
    skipped."""
    state, world, _player = _seeded("l48_band_adequate")
    monkeypatch.setattr(drop_routes_module, "drop_fight_winnable", lambda rested, gd, monster: True)
    dear = (("lich_crown", 1),)
    real = drop_routes_module.monster_doors
    monkeypatch.setattr(drop_routes_module, "monster_doors",
                        lambda m, s, g: (dear, *real(m, s, g)) if m == "lich" else real(m, s, g))
    ctx = TIMED_NO_PROFILE_CONTEXT
    (option,) = route_options("life_crystal_shard", state, world, ctx, policy=PIECE_POLICY)
    assert option.unlock == "door:lich_tomb_keyx1"
    assert route_options("life_crystal_shard", state, world, ctx, policy=PIECE_POLICY,
                         opening=frozenset({LICH_DOOR, dear})) == []


# --- the executor serves what the walk routed --------------------------------

def test_the_plan_fetches_the_key_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """The decomposition of a `life_crystal_shard` gather opens the lich door:
    its plan fights for the key (a key dropper, never the lich) and stops
    there, and the next cycle, holding the key, crosses and fights the lich.
    The level-30 sheet: the lich (level 30) is not grey for it."""
    state, world, player = _seeded("l30_band_entry")
    monkeypatch.setattr(drop_routes_module, "drop_fight_winnable", lambda rested, gd, monster: True)
    goal = GatherMaterialsGoal("life_crystal_shard", {"life_crystal_shard": 1})
    ctx = player._selection_context()
    plan = decompose(goal, state, world, player._build_actions(), ctx)
    assert plan is not None
    fights = [a.monster_code for a in plan if isinstance(a, FightAction)]
    keyers = {m for m, *_ in world.monsters_dropping("lich_tomb_key")}
    assert fights and set(fights) <= keyers
    holding = replace(state, inventory={**state.inventory, "lich_tomb_key": 1})
    plan = decompose(goal, holding, world, player._build_actions(), ctx)
    assert plan is not None
    assert any(isinstance(a, MapTransitionAction) for a in plan)
    assert [a.monster_code for a in plan if isinstance(a, FightAction)][-1] == "lich"


def test_a_fee_door_is_opened_by_fighting_for_its_gold() -> None:
    """`dryad_hair` drops only from the dryad, past the 5000-gold door the
    level-48 pocket cannot pay. A piece's walk fights for gold (`fight_gold`),
    so its plan opens the door with one gold fight; a walk that cannot earn
    gold leaves the door a wall, named as before."""
    state, world, player = _seeded("l48_band_adequate")
    assert state.gold < 5000
    piece = GatherMaterialsGoal("dryad_hair", {"dryad_hair": 1}, piece_material=True,
                                fight_gold=True)
    plan = decompose(piece, state, world, player._build_actions(), player._selection_context())
    assert plan is not None
    (fight,) = plan
    assert isinstance(fight, FightAction) and fight.gold_target is not None
    declined: list[str] = []
    plain = GatherMaterialsGoal("dryad_hair", {"dryad_hair": 1})
    assert decompose(plain, state, world, player._build_actions(), player._selection_context(),
                     declined) is None
    assert declined == ["infeasible:dryad_hair:no_route:dryad_hair"]


def test_the_census_reaches_past_the_doors_the_walk_opens() -> None:
    """`craft_completeness._census_reach`: the walk's reach now, plus the
    regions past a door the decomposition's walk can open. The level-30
    sheet can fight for the lich tomb key, not for the 5000-gold fee."""
    state, world, _player = _seeded("l30_band_entry")
    reach = craft_completeness._census_reach(state, world)
    assert reach > reachable_regions_now(state, world)
    assert "underground:9,7" in reach
    assert "restricted:overworld:-5,8" not in reach


# --- ruling T14e-1: the door leg is one priced route among the rest -----------

def _rare_ready_dropper(monkeypatch: pytest.MonkeyPatch) -> None:
    """`life_crystal_shard` also drops, 1 in 5000, from the reachable cyclops:
    a ready route far dearer than the lich past its door. Every fight wins."""
    real = GameData.monsters_dropping
    monkeypatch.setattr(GameData, "monsters_dropping", lambda self, item: real(self, item) + (
        [("cyclops", 5000, 1, 1)] if item == "life_crystal_shard" else []))
    monkeypatch.setattr(drop_routes_module, "drop_fight_winnable", lambda rested, gd, monster: True)


def test_a_door_route_cheaper_than_a_ready_one_is_the_price_and_the_route_served(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A ready route no longer hides a door: both are priced, the cheaper door
    leg is the price, and the walk serves it (`door_route` is its `prefer`):
    the plan fights for the key, not the cyclops."""
    state, world, player = _seeded("l30_band_entry")
    _rare_ready_dropper(monkeypatch)
    ctx = player._selection_context()
    options = route_options("life_crystal_shard", state, world, ctx, policy=DECOMPOSE_POLICY)
    assert [(o.venue, o.unlock) for o in options] == [("cyclops", ""),
                                                      ("lich", "door:lich_tomb_keyx1")]
    assert door_route("life_crystal_shard", state, world, ctx, policy=DECOMPOSE_POLICY,
                      pocket=state.gold) == (SourceKind.DROP, "lich")
    plan = decompose(GatherMaterialsGoal("life_crystal_shard", {"life_crystal_shard": 1}),
                     state, world, player._build_actions(), ctx)
    assert plan is not None
    fights = [a.monster_code for a in plan if isinstance(a, FightAction)]
    keyers = {m for m, *_ in world.monsters_dropping("lich_tomb_key")}
    assert fights and set(fights) <= keyers


def test_a_ready_route_the_door_cannot_beat_is_the_one_served(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """An item a ready route serves at no more per unit than a door route: the
    door route is dominated and not priced (a gold fight past the 5000-gold
    door against the ready gold fights), and `door_route` is None."""
    state, world, player = _seeded("l30_band_entry")
    ctx = player._selection_context()
    gold = route_options(GOLD_CODE, state, world, ctx, policy=PIECE_POLICY)
    assert gold and not [o for o in gold if o.unlock]
    assert door_route("copper_ore", state, world, ctx, policy=DECOMPOSE_POLICY,
                      pocket=state.gold) is None


def test_a_door_route_never_suppresses_the_gear_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """The gear gate asks whether anything served the item before a door was
    priced: an item a door route serves still gets its gear-gated drop."""
    state, world, _player = _seeded("l30_band_entry")
    monkeypatch.setattr(drop_routes_module, "drop_fight_winnable", lambda rested, gd, monster: True)
    gear = replace(route_options("life_crystal_shard", state, world, TIMED_NO_PROFILE_CONTEXT,
                                 policy=DECOMPOSE_POLICY)[0], unlock="gear:x")
    monkeypatch.setattr(acquisition_cost, "_gated_drop_option", lambda *a: gear)
    options = route_options("life_crystal_shard", state, world, TIMED_NO_PROFILE_CONTEXT,
                            policy=DECOMPOSE_POLICY)
    assert [o.unlock for o in options] == ["door:lich_tomb_keyx1", "gear:x"]
    assert route_options("life_crystal_shard", state, world, TIMED_NO_PROFILE_CONTEXT,
                         gated_drop=False, policy=DECOMPOSE_POLICY)[-1].unlock != "gear:x"


def test_a_monster_past_a_door_it_cannot_yet_beat_pays_the_door_and_the_gear(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The cultist_alchemist shape: the lich past its door, unwinnable at
    level 30. Its route pays both unlocks under one key, the door's and the
    gear's; with no closing gear (or no gear gate) it is no route."""
    state, world, _player = _seeded("l30_band_entry")
    ctx = TIMED_NO_PROFILE_CONTEXT
    model = ObtainModel(state, world, ctx, datetime.now(UTC))
    ((_route, unmet),) = model.past_a_door("life_crystal_shard", DECOMPOSE_POLICY,
                                          acquisition_cost._DOOR_COMPANIONS)
    assert {g.kind for g in unmet} == {GateKind.SPAWN_KNOWN, GateKind.WINNABLE}
    door = acquisition_cost.door_price(LICH_DOOR, state, world, ctx, None, DECOMPOSE_POLICY,
                                       True, frozenset())
    monkeypatch.setattr(acquisition_cost, "_gear_unlock", lambda monster, *a: 7)
    (option,) = [o for o in route_options("life_crystal_shard", state, world, ctx,
                                          policy=DECOMPOSE_POLICY) if o.venue == "lich"]
    assert (option.unlock, option.unlock_actions) == ("door:lich_tomb_keyx1+gear:lich", door + 7)
    assert not [o for o in route_options("life_crystal_shard", state, world, ctx,
                                         gated_drop=False, policy=DECOMPOSE_POLICY)
                if o.venue == "lich"]
    monkeypatch.setattr(acquisition_cost, "_gear_unlock", lambda monster, *a: None)
    assert not [o for o in route_options("life_crystal_shard", state, world, ctx,
                                         policy=DECOMPOSE_POLICY) if o.venue == "lich"]


class _RatedStore:
    """The two grind-rate reads `_climb_actions` asks of a store."""

    def __init__(self, own: float | None, fleet: float | None) -> None:
        self.own, self.fleet = own, fleet

    def skill_grind_rate(self, skill: str) -> float | None:
        return self.own

    def fleet_skill_grind_rate(self, skill: str) -> float | None:
        return self.fleet


def test_a_gather_past_a_door_pays_its_climb_as_the_skill_gate_does() -> None:
    """A GATHER_SKILL gate beside a door is paid with the climb
    `_gated_skill_option` charges (`_climb_actions`), keyed by the skill; with
    no store, or no rate, it cannot be paid."""
    state = replace(make_state(), skills={"mining": 1}, skill_xp={"mining": 0},
                    skill_max_xp={"mining": 100})
    route = drop_routes_module.Route("ore", SourceKind.GATHER, "rocks", 1, 1, ())
    gate = Gate(GateKind.GATHER_SKILL, "mining", False, 5)
    world = GameData()
    unlock = acquisition_cost._companion_unlock
    store = _RatedStore(None, 10.0)
    paid = unlock(route, gate, state, world, TIMED_NO_PROFILE_CONTEXT, store,  # type: ignore[arg-type]
                  DECOMPOSE_POLICY, True, frozenset())
    assert paid is not None and paid[0] == "skill:mining:5" and paid[1] > 0
    assert unlock(route, gate, state, world, TIMED_NO_PROFILE_CONTEXT, None, DECOMPOSE_POLICY,
                  True, frozenset()) is None
    assert unlock(route, gate, state, world, TIMED_NO_PROFILE_CONTEXT,
                  _RatedStore(None, None), DECOMPOSE_POLICY, True,  # type: ignore[arg-type]
                  frozenset()) is None


def test_the_gear_past_a_door_never_reprices_that_door(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ruling T14e-m5: the gear chain that opens a fight past a door is priced
    with the door closed to it (`opening`). A chain that needs the very item
    the door's route yields cannot be had through that door: no route, and no
    loop."""
    state, world, _player = _seeded("l30_band_entry")
    step = DeficitStep("life_crystal_shard", "ring", 30, None, 0, 1)
    monkeypatch.setattr(acquisition_cost, "combat_deficit",
                        lambda s, g, monster: CombatDeficit(monster, -1, (step,), True))
    assert not [o for o in route_options("life_crystal_shard", state, world,
                                         TIMED_NO_PROFILE_CONTEXT, policy=DECOMPOSE_POLICY)
                if o.venue == "lich"]

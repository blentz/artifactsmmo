"""A skill climb first fetches its best tool (spec 2026-10-18 §2.6, plan B
Task 8): `tool_target` is data-driven on `skill_effects`, the owned best tool is
never re-acquired, and the walk roots `ObtainItem(tool)` in front of the climb.

Prospecting is the drop work's tool (§2.8, plan B Task 12b): `drop_tool_target`
names the prospecting item that pays for itself on a route's remaining drop
work, and the walk offers it before that work.
"""

from dataclasses import replace
from datetime import UTC, datetime
from fractions import Fraction

import pytest

from artifactsmmo_cli.ai.acquisition_cost import drop_work, drop_work_actions
from artifactsmmo_cli.ai.decisions.root import RootWalk
from artifactsmmo_cli.ai.decisions.which_piece_is_next import fleet_piece_root
from artifactsmmo_cli.ai.fleet_piece import FleetPiece
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_objective_result import GearPiece
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.obtain_model.policy import PIECE_POLICY
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachSkillLevel, no_decline
from artifactsmmo_cli.ai.tool_objective import (
    drop_tool_first,
    drop_tool_target,
    tool_first,
    tool_target,
)
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_decisions_root import _gd
from tests.test_ai.test_decisions_which_piece import SHIELD, _missing, _resolve
from tests.test_ai.test_strategy_driver import _ctx

HAMMER = "gear_hammer"
NOW = datetime(2026, 10, 25, tzinfo=UTC)


def _world(*, effect: int = -10, level: int = 1, skill: str = "gearcrafting") -> GameData:
    """`_gd()` plus a craftable tool whose only mark is its `skill_effects`."""
    gd = _gd()
    gd._item_stats = {**gd._item_stats, HAMMER: ItemStats(
        code=HAMMER, level=level, type_="weapon", skill_effects={skill: effect},
        crafting_skill="weaponcrafting", crafting_level=1)}
    gd._crafting_recipes = {**gd._crafting_recipes, HAMMER: {"ash_plank": 4}}
    return gd


def test_a_craft_skill_tool_qualifies_by_its_effect() -> None:
    gd = _world()
    state = make_state(level=15)
    assert tool_target("gearcrafting", state, gd, _ctx(), NOW) == HAMMER
    assert tool_target("mining", state, gd, _ctx(), NOW) is None


def test_a_climb_first_fetches_its_tool() -> None:
    gd = _world()
    resolution = _resolve(make_state(level=15), gd, _missing(SHIELD))
    assert resolution.root == ObtainItem(HAMMER, 1)
    assert resolution.blocked_target == "iron_shield"


def test_an_owned_tool_is_never_reacquired() -> None:
    gd = _world()
    climb = ReachSkillLevel(skill="gearcrafting", level=2)
    for owned in (make_state(level=15, bank_items={HAMMER: 1}),
                  make_state(level=15, inventory={HAMMER: 1}),
                  make_state(level=15, equipment={"weapon_slot": HAMMER})):
        assert tool_target("gearcrafting", owned, gd, _ctx(), NOW) is None
        assert _resolve(owned, gd, _missing(SHIELD)).root == climb


def test_a_tool_above_the_level_or_without_effect_is_no_target() -> None:
    state = make_state(level=15)
    assert tool_target("gearcrafting", state, _world(level=16), _ctx(), NOW) is None
    assert tool_target("gearcrafting", state, _world(effect=0), _ctx(), NOW) is None


def test_an_unachievable_tool_is_no_target() -> None:
    gd = _world()
    gd._crafting_recipes = {**gd._crafting_recipes, HAMMER: {"leather": 4}}
    assert tool_target("gearcrafting", make_state(level=15), gd, _ctx(), NOW) is None


def test_the_best_achievable_tool_wins_over_a_better_unreachable_one() -> None:
    gd = _world()
    gd._item_stats = {**gd._item_stats, "mythic_hammer": ItemStats(
        code="mythic_hammer", level=1, type_="weapon", skill_effects={"gearcrafting": -50},
        crafting_skill="weaponcrafting", crafting_level=1)}
    gd._crafting_recipes = {**gd._crafting_recipes, "mythic_hammer": {"leather": 4}}
    assert tool_target("gearcrafting", make_state(level=15), gd, _ctx(), NOW) == HAMMER


def test_a_better_owned_tool_leaves_nothing_to_fetch_and_a_tie_prefers_it() -> None:
    gd = _world()
    gd._item_stats = {**gd._item_stats, "twin_hammer": ItemStats(
        code="twin_hammer", level=1, type_="weapon", skill_effects={"gearcrafting": -10})}
    state = make_state(level=15, inventory={"twin_hammer": 1})
    assert tool_target("gearcrafting", state, gd, _ctx(), NOW) is None


def test_the_better_unowned_tool_is_fetched_over_a_worse_owned_one() -> None:
    gd = _world(effect=-20)
    gd._item_stats = {**gd._item_stats, "old_hammer": ItemStats(
        code="old_hammer", level=1, type_="weapon", skill_effects={"gearcrafting": -10})}
    state = make_state(level=15, inventory={"old_hammer": 1})
    assert tool_target("gearcrafting", state, gd, _ctx(), NOW) == HAMMER


def test_the_climb_is_substituted_by_its_tool() -> None:
    gd = _world()
    state = make_state(level=15)
    assert tool_first(ReachSkillLevel(skill="gearcrafting", level=2), state, gd, _ctx(), NOW, no_decline) \
        == ObtainItem(HAMMER, 1)


def test_a_crafters_climb_in_front_of_a_fleet_piece_fetches_the_tool() -> None:
    gd = _world()
    piece = FleetPiece(code="iron_shield", skill="gearcrafting", level=10, gain=Fraction(1))
    state = make_state(level=15)
    assert fleet_piece_root(piece, state, gd, _ctx(), RootWalk(), None) == ObtainItem(HAMMER, 1)
    banked = replace(state, bank_items={HAMMER: 1})
    assert fleet_piece_root(piece, banked, gd, _ctx(), RootWalk(), None) == ReachSkillLevel(
        skill="gearcrafting", level=2)


def test_a_fishing_climb_fetches_the_fishing_net() -> None:
    gd = _gd()
    gd._item_stats = {**gd._item_stats, "fishing_net": ItemStats(
        code="fishing_net", level=1, type_="weapon", skill_effects={"fishing": -10},
        crafting_skill="weaponcrafting", crafting_level=1)}
    gd._crafting_recipes = {**gd._crafting_recipes, "fishing_net": {"ash_plank": 4}}
    climb = ReachSkillLevel(skill="fishing", level=2)
    assert tool_first(climb, make_state(level=15), gd, _ctx(), NOW, no_decline) == ObtainItem("fishing_net", 1)
    assert tool_first(climb, make_state(level=15, bank_items={"fishing_net": 1}), gd,
                      _ctx(), NOW, no_decline) == climb


def _refuse_tool(root):
    return "no plan this cycle" if root == ObtainItem(HAMMER, 1) else None


def test_a_declined_tool_step_falls_back_to_the_plain_climb() -> None:
    """The tool is model-feasible, but its step is declined this cycle (T8a):
    the root is the climb, and the piece is not declined for its tool."""
    gd = _world()
    state = make_state(level=15)
    resolution = _resolve(state, gd, _missing(SHIELD), decline={ObtainItem(HAMMER, 1): "no plan"})
    assert resolution.root == ReachSkillLevel(skill="gearcrafting", level=2)
    assert resolution.declined == ()
    assert tool_first(ReachSkillLevel(skill="gearcrafting", level=2), state, gd, _ctx(), NOW,
                      _refuse_tool) == ReachSkillLevel(skill="gearcrafting", level=2)


def test_a_declined_tool_step_leaves_a_fleet_climb_plain() -> None:
    gd = _world()
    piece = FleetPiece(code="iron_shield", skill="gearcrafting", level=10, gain=Fraction(1))
    walk = RootWalk(step_decline=_refuse_tool, now=NOW)
    assert fleet_piece_root(piece, make_state(level=15), gd, _ctx(), walk, None) == ReachSkillLevel(
        skill="gearcrafting", level=2)


CHARM = "lucky_charm"
RING = GearPiece("ring1_slot", "pearl_ring", 0, Fraction(1), Fraction(10), SourceKind.CRAFT)
"""Crafted from 20 small pearls, each 1 in 300 off `trout_spot`."""
PEARLS = (("trout_spot", "small_pearl", 20),)
"""The ring's drop work: 6,000 gathers at the API prior, 4,000 at +50
prospecting once `k = 1/100` is learned (a multiplier of 3/2)."""
LEARNED = LearnedDrops((), (), Fraction(1, 100))


def _pearl_world(*, planks: int = 1, level: int = 1, prospecting: int = 50) -> GameData:
    """`_gd()` plus a pearl fishery and a craftable prospecting artifact whose
    price grows with its `planks`."""
    gd = _gd()
    gd._item_stats = {**gd._item_stats,
                      CHARM: ItemStats(code=CHARM, level=level, type_="artifact",
                                       prospecting=prospecting,
                                       crafting_skill="weaponcrafting", crafting_level=1),
                      "small_pearl": ItemStats(code="small_pearl", level=1, type_="resource"),
                      "gudgeon": ItemStats(code="gudgeon", level=1, type_="resource"),
                      "pearl_ring": ItemStats(code="pearl_ring", level=1, type_="ring",
                                              resistance={"water": 3},
                                              crafting_skill="gearcrafting", crafting_level=1)}
    gd._crafting_recipes = {**gd._crafting_recipes, CHARM: {"ash_plank": planks},
                            "pearl_ring": {"small_pearl": 20}}
    gd._resource_drops = {**gd._resource_drops, "trout_spot": "gudgeon"}
    gd._resource_drops_full = {"trout_spot": [("gudgeon", 1, 1, 1), ("small_pearl", 300, 1, 1)]}
    gd._resource_skill = {**gd._resource_skill, "trout_spot": ("fishing", 1)}
    gd._resource_locations = {**gd._resource_locations, "trout_spot": [(3, 0)]}
    return gd


def _learned(k: Fraction = Fraction(1, 100)):
    return replace(_ctx(), learned_drops=LearnedDrops((), (), k))


def test_a_prospecting_item_comes_first_only_when_it_saves_time() -> None:
    """The same 20 pearls: a charm a few actions dear saves 2,000 gathers, so
    it comes first; one dearer than the 2,000 it saves never does."""
    state = make_state(level=15)
    assert drop_tool_target(PEARLS, state, _pearl_world(), _learned()) == CHARM
    assert drop_tool_target(PEARLS, state, _pearl_world(planks=2500), _learned()) is None


def test_the_saving_is_read_on_top_of_the_worn_prospecting() -> None:
    """`P` is the worn total: at P = 50 the pearls are 4,000 gathers and the
    charm's +50 takes them to 3,000, a saving it still pays for."""
    state = make_state(level=15, prospecting=50)
    assert drop_tool_target(PEARLS, state, _pearl_world(), _learned()) == CHARM


def test_no_learned_slope_means_prospecting_saves_nothing(monkeypatch) -> None:
    """`k = 0` (no prospecting evidence fitted): the work costs the same at any
    prospecting, so no item is named, and none is even priced."""
    def _unpriced(*_args, **_kwargs):
        raise AssertionError("a prospecting item was priced though it saves nothing")
    monkeypatch.setattr("artifactsmmo_cli.ai.tool_objective.acquisition_actions", _unpriced)
    assert drop_tool_target(PEARLS, make_state(level=15), _pearl_world(),
                            _learned(Fraction(0))) is None


def test_an_owned_or_level_illegal_prospecting_item_is_never_returned() -> None:
    gd = _pearl_world()
    for owned in (make_state(level=15, inventory={CHARM: 1}),
                  make_state(level=15, bank_items={CHARM: 1}),
                  make_state(level=15, equipment={"artifact1_slot": CHARM})):
        assert drop_tool_target(PEARLS, owned, gd, _learned()) is None
    assert drop_tool_target(PEARLS, make_state(level=15), _pearl_world(level=16),
                            _learned()) is None


def test_an_owned_stronger_item_leaves_a_weaker_one_unfetched() -> None:
    gd = _pearl_world(prospecting=20)
    gd._item_stats = {**gd._item_stats, "old_charm": ItemStats(
        code="old_charm", level=1, type_="artifact", prospecting=50)}
    assert drop_tool_target(PEARLS, make_state(level=15), gd, _learned()) == CHARM
    owned = make_state(level=15, bank_items={"old_charm": 1})
    assert drop_tool_target(PEARLS, owned, gd, _learned()) is None


def test_the_strongest_item_that_pays_for_itself_is_named() -> None:
    """A stronger charm too dear to pay for itself is passed over for a weaker,
    cheap one; when both pay, the stronger wins."""
    gd = _pearl_world()
    gd._item_stats = {**gd._item_stats, "great_charm": ItemStats(
        code="great_charm", level=1, type_="artifact", prospecting=100,
        crafting_skill="weaponcrafting", crafting_level=1)}
    gd._crafting_recipes = {**gd._crafting_recipes, "great_charm": {"ash_plank": 2500}}
    assert drop_tool_target(PEARLS, make_state(level=15), gd, _learned()) == CHARM
    gd._crafting_recipes = {**gd._crafting_recipes, "great_charm": {"ash_plank": 1}}
    assert drop_tool_target(PEARLS, make_state(level=15), gd, _learned()) == "great_charm"


def test_an_unobtainable_item_never_pays_however_large_the_work() -> None:
    """20,000 pearls save 2,000,000 gathers at +50: more than the no-route
    sentinel a charm with no source is priced at, which is still no price."""
    gd = _pearl_world()
    gd._crafting_recipes = {**gd._crafting_recipes, CHARM: {"leather": 1}}
    work = (("trout_spot", "small_pearl", 20_000),)
    assert drop_tool_target(work, make_state(level=15), gd, _learned()) is None


def test_the_drop_work_is_the_routes_remaining_gathers() -> None:
    """The ring's route is its craft from 20 pearls fished at `trout_spot`; a
    pearl in the bag is work already done."""
    gd = _pearl_world()
    state = make_state(level=15)
    assert drop_work("pearl_ring", 1, state, gd, _learned(), None, policy=PIECE_POLICY) == PEARLS
    held = replace(state, inventory={"small_pearl": 5})
    assert drop_work("pearl_ring", 1, held, gd, _learned(), None, policy=PIECE_POLICY) == (
        ("trout_spot", "small_pearl", 15),)


def test_drop_tool_first_offers_the_item_unless_its_step_is_declined() -> None:
    step = ObtainItem("pearl_ring", 1, slot="ring1_slot")
    state = make_state(level=15)
    assert drop_tool_first(step, PEARLS, state, _pearl_world(), _learned(), no_decline) == \
        ObtainItem(CHARM, 1)
    refuse = {ObtainItem(CHARM, 1): "no plan"}.get
    assert drop_tool_first(step, PEARLS, state, _pearl_world(), _learned(), refuse) == step
    assert drop_tool_first(step, PEARLS, state, _pearl_world(planks=2500), _learned(),
                           no_decline) == step


def test_the_walk_offers_the_prospecting_item_before_the_drop_work() -> None:
    """The ring's step is its craft; the charm that pays for itself on the
    ring's pearls heads the walk instead, and a declined charm leaves the
    ring's own step (an accelerator, never a gate: ruling T8a)."""
    gd = _pearl_world()
    state = make_state(level=15)
    resolution = _resolve(state, gd, _missing(RING), ctx=_learned())
    assert resolution.root == ObtainItem(CHARM, 1)
    assert resolution.trail == ("WhichPieceIsNext", "IsThisTargetBlocked")
    declined = _resolve(state, gd, _missing(RING), decline={ObtainItem(CHARM, 1): "no plan"},
                        ctx=_learned())
    assert declined.root == ObtainItem("pearl_ring", 1, slot="ring1_slot")
    assert declined.declined == ()
    plain = _resolve(state, gd, _missing(RING), ctx=_learned(Fraction(0)))
    assert plain.root == ObtainItem("pearl_ring", 1, slot="ring1_slot")


def test_a_fleet_pieces_craft_fetches_the_prospecting_item_first() -> None:
    gd = _pearl_world()
    piece = FleetPiece(code="pearl_ring", skill="gearcrafting", level=1, gain=Fraction(1))
    state = make_state(level=15)
    assert fleet_piece_root(piece, state, gd, _learned(), RootWalk(now=NOW), None) == \
        ObtainItem(CHARM, 1)
    walk = RootWalk(step_decline={ObtainItem(CHARM, 1): "no plan"}.get, now=NOW)
    assert fleet_piece_root(piece, state, gd, _learned(), walk, None) == ObtainItem("pearl_ring", 1)


@pytest.mark.parametrize("k", [Fraction(1, 100)])
def test_the_saving_is_the_one_drop_models(k) -> None:
    """`drop_work_actions` reads `ctx.drops()`: 20 pearls are 6,000 gathers at
    P = 0 and 4,000 at P = 50 with the slope learned."""
    gd = _pearl_world()
    state = make_state(level=15)
    assert drop_work_actions(PEARLS, state, gd, _learned(k)) == 6000
    assert drop_work_actions(PEARLS, replace(state, prospecting=50), gd,
                                            _learned(k)) == 4000

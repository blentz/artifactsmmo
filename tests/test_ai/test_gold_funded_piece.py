"""A gold-funded piece is served by fighting for its gold (plan B Task 15).

`lifesteal_rune` sells for 20000 gold, and `PIECE_POLICY` prices it through
gold earned by fighting (ruling T2a). Until this task the executor's walk had
no gold-fight leg, so the rune headed `L*` and was declined
`infeasible:lifesteal_rune:no_route:` every cycle. Ruling T3a: only that
piece's goal may fight for gold; its leg fights the monster the price fought;
one fight a cycle, re-decided each cycle (T15b); the buy keeps the reserve.
Ruling T15a: the gold a price counts is gold from a fight the executor would
take, at most `FIGHT_LEVEL_GAP_CEILING` levels above the character.
"""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

from artifactsmmo_cli.ai import accumulation_sell, craft_plan_gen
from artifactsmmo_cli.ai.acquisition_cost import acquisition_options, fight_gold_monster
from artifactsmmo_cli.ai.acquisition_cost_core import priced_route
from artifactsmmo_cli.ai.actions.combat import FIGHT_LEVEL_GAP_CEILING, FightAction, win_gold
from artifactsmmo_cli.ai.actions.ge_fill_sell import GeFillSellOrderAction
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.decompose_core import Act
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective_result import GearObjective, GearPiece
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.obtain_item_routing import _equippable_goal
from artifactsmmo_cli.ai.obtain_model.policy import DECOMPOSE_POLICY, PIECE_POLICY
from artifactsmmo_cli.ai.plan_cache import PlanCache, cache_holdings
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.progression_reserve import spendable_pocket
from artifactsmmo_cli.ai.scenario import (
    FAR_FUTURE,
    SCENARIOS,
    load_bundle_game_data,
    scenario_state,
)
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT
from tests.test_ai.shared_world import attached, shared_world

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"

CELL = "l20_dual_utility"
"""A level-20 character with 100 gold whose `L*` heads with the rune."""

RUNE = ObtainItem("lifesteal_rune", 1, slot="rune_slot")
PRICE = 20000
COVERED = 20100
"""The pocket at which the buy passes the reserve: the price plus the 100-gold
safety floor (the rune is itself the reserved target, so its own price is
credited back)."""

GOLD_MONSTER = "highwayman"
"""The cheapest gold per action a level-20 character would fight: level 15,
4 gold a win."""

CAPPED = "imp"
"""Cheaper gold per action than the highwayman, and level 28: above the
level-20 character's fight ceiling, so no price counts its gold."""

SOLD = "sap"
SELLER = "timber_merchant"
"""An item and its (event) buyer: the SELL fixture of ruling T15e."""

OTHER_RUNE = "healing_rune"
"""A recipe-less rune sold for gold (10000 at the rune vendor) that is not in
the cell's `L*`."""


def _world() -> GameData:
    sc = SCENARIOS[CELL]
    world = shared_world(BUNDLE, with_ge_orders=sc.ge_market,
                         completed_achievements=frozenset(sc.unlocked_achievements))
    world.active_event_codes = set(sc.active_events)
    world.active_raid_codes = {code for code, _boss in sc.raids}
    return world


def _player(world: GameData, gold: int | None = None) -> GamePlayer:
    player = GamePlayer(character=CELL, history=None)
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    state = scenario_state(SCENARIOS[CELL], world)
    player.seed_offline(state if gold is None else replace(state, gold=gold), world)
    return player


def _state(world: GameData) -> WorldState:
    player = _player(world)
    assert player.state is not None
    return player.state


def test_a_gold_funded_buy_is_served() -> None:
    """The rune roots a plan whose one action is a win against the price's gold
    monster, armed on one win's mean gold; nothing is declined."""
    world = _world()
    report = _player(world).plan_from_state()
    assert report.decision.declined == ()
    assert report.decision.chosen_root == RUNE
    assert [repr(a) for a in report.plan] == [f"Fight({GOLD_MONSTER})"]
    fight = report.plan[0]
    assert isinstance(fight, FightAction)
    assert fight.gold_target == win_gold(GOLD_MONSTER, world) == 4
    assert fight.drop_farm is False


def test_the_buy_follows_once_the_pocket_covers_it() -> None:
    """The buy is planned once the pocket covers the price above the reserve
    `NpcBuy` keeps (`can_spend`); one gold short, the plan still fights."""
    world = _world()
    state = _state(world)
    assert spendable_pocket(replace(state, gold=COVERED), world, frozenset({RUNE.code})) == PRICE
    assert spendable_pocket(replace(state, gold=COVERED - 1), world,
                            frozenset({RUNE.code})) == PRICE - 1
    covered = _player(world, COVERED).plan_from_state()
    assert [repr(a) for a in covered.plan] == ["NpcBuy(lifesteal_rune×1@rune_vendor)"]
    short = _player(world, COVERED - 1).plan_from_state()
    assert [repr(a) for a in short.plan] == [f"Fight({GOLD_MONSTER})"]


def test_the_gold_monster_is_the_one_that_priced_it() -> None:
    """The served monster is the argmin of the rune's own priced gold routes,
    by exact cost per gold, first of equal costs."""
    world = _world()
    state = _state(world)
    ctx = attached(state, world, TIMED_NO_PROFILE_CONTEXT, None)
    gold = acquisition_options(RUNE.code, state, world, ctx, None, policy=PIECE_POLICY)["gold"]
    best = min(gold, key=lambda r: Fraction(r.actions_per_application) / r.yield_per)
    assert best.venue == GOLD_MONSTER
    assert fight_gold_monster(state, world, ctx, policy=PIECE_POLICY) == GOLD_MONSTER
    # A policy that earns no gold by fighting names no gold monster.
    assert fight_gold_monster(state, world, ctx, policy=DECOMPOSE_POLICY) is None


def test_gold_fights_stay_under_the_fight_ceiling() -> None:
    """Ruling T15a: the imp pays gold cheaper per action than any other monster,
    and is 8 levels above the character; no gold route counts it, so the price
    and the served fight are the highwayman's."""
    world = _world()
    state = _state(world)
    ctx = attached(state, world, TIMED_NO_PROFILE_CONTEXT, None)
    ceiling = state.level + FIGHT_LEVEL_GAP_CEILING
    assert world.monster_level(CAPPED) > ceiling
    assert world.monster_max_gold(CAPPED) > 0
    gold = acquisition_options("gold", state, world, ctx, None, policy=PIECE_POLICY)["gold"]
    assert all(world.monster_level(r.venue) <= ceiling for r in gold if r.kind == "gold_drop")
    assert CAPPED not in {r.venue for r in gold}
    lifted = replace(state, level=world.monster_level(CAPPED) - FIGHT_LEVEL_GAP_CEILING)
    lifted_ctx = attached(lifted, world, TIMED_NO_PROFILE_CONTEXT, None)
    assert CAPPED in {r.venue for r in acquisition_options(
        "gold", lifted, world, lifted_ctx, None, policy=PIECE_POLICY)["gold"]}


def test_gold_fight_is_only_for_the_piece() -> None:
    """`DECOMPOSE_POLICY` still has no gold fight: the same rune goal without
    the piece's flag is declined as before, and only the flagged goal fights."""
    assert DECOMPOSE_POLICY.fight_gold is False
    world = _world()
    player = _player(world)
    state = player.state
    assert state is not None
    ctx = attached(state, world, TIMED_NO_PROFILE_CONTEXT, None)
    actions = player._build_actions()
    declined: list[str] = []
    plain = GatherMaterialsGoal(RUNE.code, {RUNE.code: 1})
    assert decompose(plain, state, world, actions, ctx, declined) is None
    assert declined == ["infeasible:lifesteal_rune:no_route:"]
    piece = GatherMaterialsGoal(RUNE.code, {RUNE.code: 1}, fight_gold=True)
    plan = decompose(piece, state, world, actions, ctx)
    assert plan is not None and [repr(a) for a in plan] == [f"Fight({GOLD_MONSTER})"]


def test_a_win_projects_its_mean_gold() -> None:
    """`FightAction.apply` adds one win's mean gold, `(min + max) // 2` of the
    API's range, not its best case."""
    world = _world()
    state = _state(world)
    low, high = world.monster_min_gold(GOLD_MONSTER), world.monster_max_gold(GOLD_MONSTER)
    assert low < high
    fight = FightAction(monster_code=GOLD_MONSTER,
                        locations=frozenset(world.all_monster_locations[GOLD_MONSTER]),
                            learned_drops=LearnedDrops.empty())
    assert fight.apply(state, world).gold == state.gold + (low + high) // 2


def test_the_gold_leg_counts_the_pocket() -> None:
    """The cache arms a gold fight on the pocket: it advances once one win's
    gold has arrived in `state.gold`, which no bag count ever shows."""
    world = _world()
    state = _state(world)
    fight = FightAction(monster_code=GOLD_MONSTER, gold_target=4,
                        locations=frozenset(world.all_monster_locations[GOLD_MONSTER]),
                            learned_drops=LearnedDrops.empty())
    cache = PlanCache(selected_goal=GatherMaterialsGoal(RUNE.code, {RUNE.code: 1}),
                      plan=[fight], crafting_target=None, plan_level=state.level,
                      goal_repr="g")
    cache.arm_step(cache_holdings(state), world)
    assert cache.step_target == state.gold + 4
    assert cache.batch_satisfied(cache_holdings(replace(state, gold=state.gold + 3)), world) is False
    assert cache.batch_satisfied(cache_holdings(replace(state, gold=state.gold + 4)), world) is True


def test_each_gold_fight_cycle_re_decides() -> None:
    """Ruling T15b: one fight per cycle. Two consecutive cycles each decide
    afresh: the first plans one win, the win's gold ends its plan, and the
    second cycle re-decides rather than repeating a committed leg."""
    world = _world()
    player = _player(world)
    state = player.state
    assert state is not None
    player._last_ctx = attached(state, world, TIMED_NO_PROFILE_CONTEXT, None)
    actions = player._build_actions()
    for _cycle in range(2):
        _goal, plan, _tried, replanned = player._plan_or_reuse(state, world, actions)
        assert replanned is True
        assert [repr(a) for a in plan] == [f"Fight({GOLD_MONSTER})"]
        state = plan[0].apply(state, world)
        cache = player._plan_cache
        assert cache is not None
        assert cache.batch_satisfied(cache_holdings(state), world) is True
        cache.advance()
        assert cache.exhausted()
        player._last_outcome = "ok"
        player.state = state


def test_a_grey_gold_monster_is_fought_as_a_drop_farm() -> None:
    """At level 39 the imp is still the cheapest gold, and pays no XP: the gold
    fight is the drop_farm variant, which the zero-XP gate lets through, as
    `select_drop_fight` hunts a grey dropper."""
    world = _world()
    seeded = _player(world)
    assert seeded.state is not None
    player = GamePlayer(character=CELL, history=None)
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    player.seed_offline(replace(seeded.state, level=39), world)
    state = player.state
    assert state is not None
    ctx = attached(state, world, TIMED_NO_PROFILE_CONTEXT, None)
    assert fight_gold_monster(state, world, ctx, policy=PIECE_POLICY) == CAPPED
    assert world.xp_per_kill(CAPPED, state.level) == 0
    piece = GatherMaterialsGoal(RUNE.code, {RUNE.code: 1}, fight_gold=True)
    plan = decompose(piece, state, world, player._build_actions(), ctx)
    assert plan is not None
    fights = [a for a in plan if isinstance(a, FightAction)]
    assert [(repr(a), a.drop_farm, a.gold_target) for a in fights] == [
        (f"Fight({CAPPED})", True, win_gold(CAPPED, world))]
    assert plan[-1] is fights[0]


def test_no_fight_for_the_gold_monster_is_a_named_decline() -> None:
    """A pool with no fight against the price's gold monster cannot serve the
    gold leg: the walk names the unmapped step rather than fighting another
    monster for it."""
    world = _world()
    player = _player(world)
    state = player.state
    assert state is not None
    ctx = attached(state, world, TIMED_NO_PROFILE_CONTEXT, None)
    actions = [a for a in player._build_actions()
               if not (isinstance(a, FightAction) and a.monster_code == GOLD_MONSTER)]
    declined: list[str] = []
    piece = GatherMaterialsGoal(RUNE.code, {RUNE.code: 1}, fight_gold=True)
    assert decompose(piece, state, world, actions, ctx, declined) is None
    assert len(declined) == 1 and declined[0].startswith("unmapped_step:Act(item='gold'"), declined


def test_a_cheaper_sale_still_names_the_cheapest_fight(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ruling T15e: when a licensed sale is gold's cheapest route, the gold leg
    is still a fight, against the cheapest fight, never no monster. The
    fixture: ten saps licensed to sell to the live timber merchant (a sap
    gathers in about 11 actions, so a gold piece by sale costs 12), and a
    fight record that loses almost every fight, so every win costs more per
    gold than that."""
    world = load_bundle_game_data(BUNDLE, with_ge_orders=SCENARIOS[CELL].ge_market,
                                  completed_achievements=frozenset(
                                      SCENARIOS[CELL].unlocked_achievements))
    world.active_event_codes = {SELLER}
    monkeypatch.setattr(accumulation_sell, "sellable_surplus", lambda *_args: {SOLD: 10})
    state = replace(scenario_state(SCENARIOS[CELL], world), active_events={SELLER: FAR_FUTURE})
    ctx = attached(state, world, TIMED_NO_PROFILE_CONTEXT, None)
    ctx = replace(ctx, fight_records=tuple((code, 100, 1) for code in world.monsters.levels))
    gold = acquisition_options("gold", state, world, ctx, None, policy=PIECE_POLICY)
    _price, cheapest = priced_route("gold", 1, gold, {})
    assert cheapest is not None and (cheapest.kind, cheapest.venue) == ("sell", SELLER)
    fights = [r for r in gold["gold"] if r.kind == "gold_drop"]
    best = min(fights, key=lambda r: Fraction(r.actions_per_application) / r.yield_per)
    assert fight_gold_monster(state, world, ctx, policy=PIECE_POLICY) == best.venue


def test_only_the_piece_is_flagged() -> None:
    """The flag is the piece's own: another recipe-less gold buy for the same
    slot, `healing_rune`, is not in `L*` and its goal does not fight for gold."""
    world = _world()
    state = _state(world)
    ctx = attached(state, world, TIMED_NO_PROFILE_CONTEXT, None)
    assert ctx.gear_objective is not None
    assert OTHER_RUNE not in {piece.code for piece in ctx.gear_objective.missing}
    assert world.crafting_recipe(OTHER_RUNE) is None
    assert world.npc_purchases(OTHER_RUNE) == [("rune_vendor", 10000, "gold")]
    piece = _equippable_goal(RUNE.code, "rune_slot", state, world, ctx)
    other = _equippable_goal(OTHER_RUNE, "rune_slot", state, world, ctx)
    assert isinstance(piece, GatherMaterialsGoal) and piece.fight_gold is True
    assert isinstance(other, GatherMaterialsGoal) and other.fight_gold is False


# --------------------------------------------------------------------------
# Ruling T14a-C: the walk serves an `L*` piece's GE-filled material.
# --------------------------------------------------------------------------

SHARD = "malefic_shard"
"""`malefic_crystal`'s price at the archaeologist (24): on the busy book a
standing sell order (3 at 800 gold) is its only route the character has."""


def _busy() -> tuple[GameData, WorldState, list[object]]:
    world = shared_world(BUNDLE, with_ge_orders=True)
    state = scenario_state(SCENARIOS[CELL], world)
    player = GamePlayer(character=state.character, history=None)
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    player.seed_offline(state, world)
    return world, state, player._build_actions()


def _crystal_ctx():  # type: ignore[no-untyped-def]
    piece = GearPiece("artifact3_slot", "malefic_crystal", 0, Fraction(1), Fraction(10),
                      SourceKind.BUY)
    return replace(TIMED_NO_PROFILE_CONTEXT, gear_objective=GearObjective(
        "wolf", {"artifact3_slot": "malefic_crystal"}, Fraction(1), (piece,)))


def test_an_l_star_piece_s_currency_step_is_served_by_its_priced_route() -> None:
    """Live R2D2 2026-10-27: `malefic_crystal` priced through 24 GE-filled
    `malefic_shard` and declined `infeasible:malefic_shard:no_route` — the
    walk had no GE fill (D-E). The piece's currency step is served under the
    piece's own routes (fight gold and GE fills, as `PIECE_POLICY` priced it)."""
    world, state, _actions = _busy()
    goal = _equippable_goal("malefic_crystal", "artifact3_slot", state, world, _crystal_ctx())
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.fight_gold is True
    assert set(goal.needed) == {SHARD}


def test_a_piece_s_ge_material_is_filled_with_the_pocket_s_gold() -> None:
    world, state, actions = _busy()
    order = world.ge_best_sell_order(SHARD)
    assert order is not None
    goal = GatherMaterialsGoal(SHARD, {SHARD: 3}, fight_gold=True)
    rich = replace(state, gold=order[1] * 3 + 1000)
    plan = decompose(goal, rich, world, actions, _crystal_ctx())
    assert plan is not None
    fills = [a for a in plan if isinstance(a, GeFillSellOrderAction)]
    assert fills == [GeFillSellOrderAction(order_id=order[0], item_code=SHARD, price=order[1],
                                           quantity=3,
                                           ge_location=world.grand_exchange_location())]
    # Short of the gold: the fight that earns it comes first.
    poor = replace(state, gold=100)
    first = decompose(goal, poor, world, actions, _crystal_ctx())
    assert first is not None
    assert isinstance(first[0], FightAction) and first[0].gold_target is not None
    # Not a piece's step: D-E stands, the walk has no GE fill.
    declined: list[str] = []
    assert decompose(GatherMaterialsGoal(SHARD, {SHARD: 3}), rich, world, actions,
                     TIMED_NO_PROFILE_CONTEXT, declined) is None
    assert declined == [f"infeasible:{SHARD}:no_route:{SHARD}"]


def test_a_fill_is_built_only_for_the_order_that_still_stands(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The GE leg names its order: an order the book no longer holds as its
    best, or a map without the exchange, builds no fill (the next cycle
    re-walks the book it has)."""
    world, state, _actions = _busy()
    order = world.ge_best_sell_order(SHARD)
    assert order is not None

    def leg(via: str, gd: GameData) -> object:
        graph = SimpleNamespace(sources={SHARD: [SimpleNamespace(kind=SourceKind.GE_FILL, via=via)]})
        return craft_plan_gen._action_for(Act(SHARD, 0, 2, 2), graph, [], [], state, gd, True,
                                          lambda _item: False)

    assert leg(order[0], world) == GeFillSellOrderAction(
        order_id=order[0], item_code=SHARD, price=order[1], quantity=2,
        ge_location=world.grand_exchange_location())
    assert leg("a-vanished-order", world) is None
    # The order stands, the map has no exchange tile.
    monkeypatch.setattr(world, "grand_exchange_location", lambda: None)
    assert leg(order[0], world) is None

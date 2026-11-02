"""Decision code reads the one cycle clock, never the wall (Task 8b, ruling C-3).

Every test here builds its context or state at a FIXED instant `T`, early in
2026, whose event window closed long before the wall clock any run of this
suite reads. A decision that followed the wall would see that window shut (or
would hand the obtain model a different instant); each test asserts the
decision follows `T`.

Two kinds of pin:

* A window pin: an event buyer whose window is open at `T` and shut at the wall
  clock. The decision is asserted to see it open at `T`, and shut once the
  clock passes `WINDOW_END` (non-vacuity: the window is what decides).
* A clock pin, for a walk whose policy reads no event window (`now` is inert
  in its verdict): the obtain model is spied on, and every model the decision
  builds is asserted to receive `T`, both as its `now` and as its context's
  `now` (a store-less `NO_PROFILE_CONTEXT` derivation carries the caller's
  instant, not the module's import instant)."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from artifactsmmo_cli.ai import (
    gear_objective,
    grind_heal_prep,
    potion_supply,
    skill_grindable,
    suppliable,
)
from artifactsmmo_cli.ai.accumulation_sell import sellable_tradeable_now
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.chosen_loadout import ChosenLoadout
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals import craft_potions
from artifactsmmo_cli.ai.goals.craft_potions import CraftPotionsGoal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.supply_bank import SupplyBankGoal
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.plan_cache import PlanCache
from artifactsmmo_cli.ai.progression import guards, means, objective, skill_grind_target, strategy
from artifactsmmo_cli.ai.progression.guards import GuardKind
from artifactsmmo_cli.ai.progression.means import MeansKind
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.shed_actions import shed_actions
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import NO_DROPS_CONTEXT, make_state

T = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
"""The cycle's instant: long before any wall clock this suite runs at."""

WINDOW_END = T + timedelta(hours=1)
"""The event's expiry: open at `T`, shut at the wall clock."""

AT_T = replace(NO_DROPS_CONTEXT, now=T)
"""A store-less context stamped at `T`."""

_EVENT_BUYER = "gemstone_merchant"


def _event_buyer_world() -> GameData:
    """An event merchant at (6, -1) that buys and sells `copper_ore`."""
    gd = GameData()
    gd._npc_event_code[_EVENT_BUYER] = _EVENT_BUYER
    gd._event_npc_spawns[_EVENT_BUYER] = (6, -1)
    gd._npc_sell_prices[_EVENT_BUYER] = {"copper_ore": 9}
    gd._npc_stock[_EVENT_BUYER] = {"copper_ore": 10}
    gd._item_stats["copper_ore"] = ItemStats(code="copper_ore", level=1, type_="resource")
    gd.world.bank_tile = (4, 1)
    gd.world.taskmaster_tiles = {"monsters": (1, 0)}
    return gd


def _at_the_buyer(**overrides: Any) -> WorldState:
    """A character on the merchant's tile holding ore, the window live to `WINDOW_END`."""
    base: dict[str, Any] = dict(x=6, y=-1, gold=1000, inventory={"copper_ore": 5},
                                inventory_max=100, active_events={_EVENT_BUYER: WINDOW_END})
    base.update(overrides)
    return make_state(**base)


def _record_obtain_clock(monkeypatch: pytest.MonkeyPatch, module: Any) -> list[tuple[datetime, datetime]]:
    """Spy `module.ObtainModel`: record each model's `(now, ctx.now)`."""
    seen: list[tuple[datetime, datetime]] = []
    real = module.ObtainModel

    def spy(state: WorldState, game_data: GameData, ctx: SelectionContext, now: datetime,
            **kwargs: Any) -> Any:
        seen.append((now, ctx.now))
        return real(state, game_data, ctx, now, **kwargs)

    monkeypatch.setattr(module, "ObtainModel", spy)
    return seen


def _record_call_clock(monkeypatch: pytest.MonkeyPatch, module: Any, name: str,
                       clock: Callable[..., datetime]) -> list[datetime]:
    """Spy `module.<name>`: record the instant `clock(*args, **kwargs)` names."""
    seen: list[datetime] = []
    real = getattr(module, name)

    def spy(*args: Any, **kwargs: Any) -> Any:
        seen.append(clock(*args, **kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(module, name, spy)
    return seen


# ── window pins ──────────────────────────────────────────────────────────────


def test_the_sell_predicate_judges_the_buyers_window_at_the_cycle_clock() -> None:
    gd = _event_buyer_world()
    assert sellable_tradeable_now(_at_the_buyer(), gd, T) is True
    assert sellable_tradeable_now(_at_the_buyer(), gd, WINDOW_END) is False


def test_the_sell_rungs_fire_on_the_contexts_clock() -> None:
    gd = _event_buyer_world()
    state = _at_the_buyer()
    assert means._fires(MeansKind.SELL_IDLE, state, gd, None, AT_T) is True
    assert means._fires(MeansKind.SELL_IDLE, state, gd, None, replace(AT_T, now=WINDOW_END)) is False
    pressed = _at_the_buyer(inventory={"copper_ore": 95})
    assert means._fires(MeansKind.SELL_PRESSURED, pressed, gd, None, AT_T) is True


def test_the_sell_relief_guard_fires_on_the_contexts_clock() -> None:
    gd = _event_buyer_world()
    locked = replace(AT_T, bank_accessible=False)
    assert guards._fires(GuardKind.SELL_RELIEF, _at_the_buyer(), gd, None, locked) is True
    assert guards._fires(GuardKind.SELL_RELIEF, _at_the_buyer(), gd, None,
                         replace(locked, now=WINDOW_END)) is False


def test_the_pools_vendor_edges_carry_the_cycle_clock() -> None:
    gd = _event_buyer_world()
    state = _at_the_buyer()
    pool = build_actions(gd, state, None, bank_accessible=True, task_exchange_min_coins=0,
                         learned_drops=LearnedDrops.empty(), now=T)
    vendors = [a for a in pool if isinstance(a, NpcBuyAction | NpcSellAction)]
    assert {type(a) for a in vendors} == {NpcBuyAction, NpcSellAction}
    assert all(a.now == T for a in vendors)
    assert all(a.is_applicable(state, gd) for a in vendors)
    late = build_actions(gd, state, None, bank_accessible=True, task_exchange_min_coins=0,
                         learned_drops=LearnedDrops.empty(), now=WINDOW_END)
    assert not any(a.is_applicable(state, gd) for a in late
                   if isinstance(a, NpcBuyAction | NpcSellAction))


def test_the_shed_routes_sale_reads_the_contexts_clock() -> None:
    gd = _event_buyer_world()
    state = _at_the_buyer()
    sales = [a for a in shed_actions("copper_ore", 5, state, gd, AT_T, bank_accessible=True)
             if isinstance(a, NpcSellAction)]
    assert [a.now for a in sales] == [T]
    assert sales[0].is_applicable(state, gd)


# ── clock pins ───────────────────────────────────────────────────────────────


def test_suppliable_walks_on_the_callers_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _record_obtain_clock(monkeypatch, suppliable)
    suppliable.is_suppliable("copper_ore", _at_the_buyer(), _event_buyer_world(), T)
    assert seen == [(T, T)]


def test_the_gear_objectives_layers_walk_on_the_contexts_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    gd = _event_buyer_world()
    gd._item_stats["copper_helmet"] = ItemStats(code="copper_helmet", level=1, type_="helmet")
    gd._crafting_recipes["copper_helmet"] = {"copper_ore": 6}
    layer_models = _record_obtain_clock(monkeypatch, gear_objective)
    supply_models = _record_obtain_clock(monkeypatch, suppliable)
    gear_objective.achievable(_at_the_buyer(), gd, AT_T)
    assert layer_models and set(layer_models) == {(T, T)}
    assert supply_models and set(supply_models) == {(T, T)}


def test_the_near_term_model_is_stamped_with_the_callers_clock() -> None:
    model = objective.near_term_model(_at_the_buyer(), _event_buyer_world(), T)
    assert (model._now, model._ctx.now) == (T, T)


def test_classify_target_walks_on_the_callers_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _record_call_clock(monkeypatch, objective, "near_term_model",
                              lambda state, game_data, now: now)
    gd = _event_buyer_world()
    objective.CharacterObjective.from_game_data(gd).classify_target("copper_ore", _at_the_buyer(), T)
    assert seen == [T]


def test_a_vendor_leaf_is_producible_while_its_window_is_open_at_the_cycle_clock() -> None:
    """`_producible` walks under `PIECE_POLICY`, which counts a live event
    vendor: the ore is a leaf only while the merchant's window is open."""
    gd = _event_buyer_world()
    state = _at_the_buyer(inventory={})
    assert strategy._producible("copper_ore", state, gd, T) is True
    assert strategy._producible("copper_ore", state, gd, WINDOW_END) is False


def test_the_step_walk_asks_producibility_on_the_contexts_clock() -> None:
    gd = _event_buyer_world()
    state = _at_the_buyer(inventory={})
    root = strategy.ObtainItem(code="copper_ore", quantity=1)
    assert strategy.actionable_step(root, state, gd, AT_T) == root
    assert strategy.actionable_step(root, state, gd, replace(AT_T, now=WINDOW_END)) is None


def test_the_rung_existence_check_walks_on_the_callers_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _record_call_clock(monkeypatch, skill_grind_target, "grind_model",
                              lambda state, game_data, now: now)
    gd = _event_buyer_world()
    gd._item_stats["copper_bar"] = ItemStats(code="copper_bar", level=1, type_="resource",
                                             crafting_skill="mining", crafting_level=1)
    gd._crafting_recipes["copper_bar"] = {"copper_ore": 10}
    skill_grind_target.has_grind_target("mining", _at_the_buyer(skills={"mining": 1}), gd, T)
    assert seen == [T]


def test_the_grindable_predicate_hands_its_clock_to_the_rung_check(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _record_call_clock(monkeypatch, skill_grindable, "has_grind_target",
                              lambda skill, state, game_data, now: now)
    skill_grindable.skill_is_grindable("alchemy", 5, _at_the_buyer(skills={"alchemy": 1}),
                                       _event_buyer_world(), T)
    assert seen == [T]


def test_the_potion_ladder_walks_on_the_callers_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    gd = _event_buyer_world()
    gd._crafting_recipes["small_potion"] = {"copper_ore": 1}
    seen = _record_obtain_clock(monkeypatch, potion_supply)
    potion_supply.feasible_runs("small_potion", 2, _at_the_buyer(), gd, T)
    assert seen == [(T, T)]
    seen.clear()
    potion_supply.prep_supplies("small_potion", 1, _at_the_buyer(), gd, AT_T)
    assert seen == [(T, T)]


def test_the_potion_goal_sizes_its_batch_on_the_guards_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _record_call_clock(monkeypatch, craft_potions, "potion_batch",
                              lambda state, game_data, loadout, now: now)
    loadout = ChosenLoadout(monster="chicken", potions=(), food=(), made_food=())
    goal = CraftPotionsGoal(loadout=loadout, game_data=_event_buyer_world(), state=_at_the_buyer(), now=T)
    goal.value(_at_the_buyer(), _event_buyer_world())
    goal.is_satisfied(_at_the_buyer())
    # The seed, the value and the unseeded satisfaction each size the batch.
    assert seen == [T, T, T]


def test_the_heal_prep_walks_on_the_contexts_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _record_obtain_clock(monkeypatch, grind_heal_prep)
    loadout = ChosenLoadout(monster="chicken", potions=(), food=(), made_food=())
    grind_heal_prep.heal_prep_goal(_at_the_buyer(), _event_buyer_world(), AT_T, loadout)
    assert seen == [(T, T)]


def test_a_gather_goals_minted_buy_carries_the_goals_clock() -> None:
    gd = _event_buyer_world()
    state = _at_the_buyer(inventory={})
    buys = [a for a in GatherMaterialsGoal("copper_ore", {"copper_ore": 1}, now=T)
            .relevant_actions([], state, gd) if isinstance(a, NpcBuyAction)]
    assert [a.now for a in buys] == [T]
    assert buys[0].is_applicable(state, gd)
    late = [a for a in GatherMaterialsGoal("copper_ore", {"copper_ore": 1}, now=WINDOW_END)
            .relevant_actions([], state, gd) if isinstance(a, NpcBuyAction)]
    assert not late[0].is_applicable(state, gd)


def test_a_piece_material_walk_keeps_the_clock() -> None:
    goal = GatherMaterialsGoal("copper_ore", {"copper_ore": 1}, now=T).for_piece()
    buys = [a for a in goal.relevant_actions([], _at_the_buyer(inventory={}), _event_buyer_world())
            if isinstance(a, NpcBuyAction)]
    assert [a.now for a in buys] == [T]


def test_a_supply_runs_production_buys_on_its_clock() -> None:
    gd = _event_buyer_world()
    state = _at_the_buyer(inventory={})
    buys = [a for a in SupplyBankGoal(item_code="copper_ore", quantity=1, demand=1, now=T)
            .relevant_actions([], state, gd) if isinstance(a, NpcBuyAction)]
    assert [a.now for a in buys] == [T]


def test_a_cached_plans_vendor_steps_move_to_the_new_cycles_clock() -> None:
    """A plan cached at `T` is re-judged at the next cycle's instant: its buy,
    applicable at `T`, is refused once the cycle clock passes the window."""
    gd = _event_buyer_world()
    state = _at_the_buyer()
    buy = NpcBuyAction(npc_code=_EVENT_BUYER, item_code="copper_ore", npc_location=(6, -1), now=T)
    rest = RestAction()
    cache = PlanCache(selected_goal=GatherMaterialsGoal("copper_ore", {"copper_ore": 6}, now=T),
                      plan=[rest, buy], crafting_target=None, plan_level=1, goal_repr="g")
    assert cache.plan[1].is_applicable(state, gd)
    cache.on_cycle_clock(WINDOW_END)
    assert cache.plan[0] is rest
    assert cache.plan[1].now == WINDOW_END and not cache.plan[1].is_applicable(state, gd)

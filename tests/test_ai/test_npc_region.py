"""An NPC's actions travel in the region of its tile (2026-10-10, found by the
conditions census, docs/PLAN_drop_fight_loadout.md): the underground sorceress
was never indexed, so fire_crystal could not be bought, and the island's
sandwhisper_trader was walked to as if in the main overworld."""

import json
from pathlib import Path

from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


def _gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def test_every_npc_has_its_tiles_region() -> None:
    gd = _gd()
    assert gd.npc_location("sorceress") == (6, 5)
    assert gd.npc_region("sorceress") == gd.region_of(6, 5, "underground") != "overworld"
    assert gd.npc_region("sandwhisper_trader") == gd.region_of(-2, 18, "overworld") != "overworld"
    assert gd.npc_region("tailor") == "overworld"
    assert gd.npc_region("nobody") == "overworld"
    # an unmet-conditional tile stays dropped (tasks_trader, tasks_farmer 0/100)
    assert gd.npc_location("tasks_trader") is None


def test_the_factory_builds_npc_actions_in_that_region() -> None:
    gd = _gd()
    actions = build_actions(gd, None, CharacterObjective.from_game_data(gd),
                            bank_accessible=True, task_exchange_min_coins=0)
    buys = {a.travel_region for a in actions
            if isinstance(a, NpcBuyAction) and a.npc_code == "sorceress"}
    assert buys == {gd.npc_region("sorceress")}
    island = {a.travel_region for a in actions
              if isinstance(a, NpcBuyAction) and a.npc_code == "sandwhisper_trader"}
    assert island == {gd.npc_region("sandwhisper_trader")}
    # no off-region NPC buys anything in the bundle: a sale's region is the
    # vendor's too, pinned on a placed tailor moved underground
    gd.world.npc_tiles["tailor"] = (6, 5)
    gd.world.npc_layers["tailor"] = "underground"
    gd.world.npc_sell_prices["tailor"] = {"cloth": 1}
    actions = build_actions(gd, None, CharacterObjective.from_game_data(gd),
                            bank_accessible=True, task_exchange_min_coins=0)
    sells = {a.travel_region for a in actions
             if isinstance(a, NpcSellAction) and a.npc_code == "tailor"}
    assert sells == {gd.npc_region("sorceress")}


def test_fire_crystal_is_bought_underground() -> None:
    gd = _gd()
    state = scenario_state(ScenarioCharacter(name="t", level=50, gold=1000,
                                             inventory={"fire_dust": 10}), gd)
    actions = build_actions(gd, state, CharacterObjective.from_game_data(gd),
                            bank_accessible=True, task_exchange_min_coins=0)
    plan = decompose(GatherMaterialsGoal(target_item="fire_crystal", needed={"fire_crystal": 1}),
                     state, gd, actions, NO_PROFILE_CONTEXT, [])
    assert plan is not None
    assert repr(plan[-1]) .startswith("NpcBuy(fire_crystal")
    assert any("underground" in repr(a) for a in plan[:-1])


def test_a_goals_craft_vs_buy_offer_travels_in_the_vendors_region() -> None:
    """GatherMaterials builds its own NpcBuy when buying beats crafting
    (small_antidote at the nomadic_merchant); placed underground, the offer
    travels there."""
    gd = _gd()
    gd.world.npc_tiles["nomadic_merchant"] = (6, 5)
    gd.world.npc_layers["nomadic_merchant"] = "underground"
    state = scenario_state(ScenarioCharacter(name="t", level=30, gold=100000), gd)
    actions = build_actions(gd, state, CharacterObjective.from_game_data(gd),
                            bank_accessible=True, task_exchange_min_coins=0)
    goal = GatherMaterialsGoal(target_item="small_antidote", needed={"small_antidote": 1})
    offers = {a.travel_region for a in goal.relevant_actions(actions, state, gd)
              if isinstance(a, NpcBuyAction) and a.item_code == "small_antidote"}
    assert offers == {gd.npc_region("nomadic_merchant")} != {"overworld"}

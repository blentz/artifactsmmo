"""End-to-end satchel integration test (C4 Task 7).

Regression guard for the original 641K-node burn: when a satchel recipe
requires jasper_crystal (a tasks_coin-bought NPC leaf) and the character
holds 0 tasks_coin, is_plannable must return False immediately (the
affordability fast-fail prunes the search). When the character holds >= 8
tasks_coin, is_plannable returns True and relevant_actions emits an
NpcBuyAction for jasper_crystal.

Satchel recipe (simplified for testing):
  satchel = {cowhide: 5, jasper_crystal: 1}
  cowhide  <- cow (monster drop, winnable)
  jasper_crystal <- tasks_trader @ 8 tasks_coin (permanent NPC vendor)
"""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.item_catalog import ItemStats
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TASKS_COIN = "tasks_coin"
JASPER = "jasper_crystal"
COWHIDE = "cowhide"
SATCHEL = "satchel"
TASKS_TRADER = "tasks_trader"
COW = "cow"

# tasks_trader sells jasper_crystal for 8 tasks_coin (permanent, non-event)
JASPER_PRICE = 8
TRADER_LOC = (1, 5)
COW_LOC = (2, 0)


def _make_satchel_game_data() -> GameData:
    """Build a minimal GameData for the satchel scenario.

    - satchel recipe: {cowhide: 5, jasper_crystal: 1}
    - satchel craftable via gearcrafting at level 1
    - cowhide drops from cow (monster, winnable at level 5)
    - jasper_crystal sold by tasks_trader for 8 tasks_coin (permanent, non-event)
    """
    gd = GameData()

    # Satchel item stats: craftable via gearcrafting at level 1
    gd._item_stats[SATCHEL] = ItemStats(
        code=SATCHEL,
        level=1,
        type_="bag",
        crafting_skill="gearcrafting",
        crafting_level=1,
    )

    # Satchel crafting recipe: {cowhide: 5, jasper_crystal: 1}
    gd._crafting_recipes[SATCHEL] = {COWHIDE: 5, JASPER: 1}

    # jasper_crystal: no crafting recipe, not a resource drop
    gd._item_stats[JASPER] = ItemStats(code=JASPER, level=1, type_="resource")

    # cowhide: no crafting recipe
    gd._item_stats[COWHIDE] = ItemStats(code=COWHIDE, level=1, type_="resource")

    # tasks_coin: task-reward currency item
    gd._item_stats[TASKS_COIN] = ItemStats(code=TASKS_COIN, level=1, type_="currency")
    gd._task_reward_item_codes = frozenset({TASKS_COIN})

    # Permanent NPC vendor: tasks_trader sells jasper_crystal for 8 tasks_coin
    gd._npc_stock[TASKS_TRADER] = {JASPER: JASPER_PRICE}
    gd._npc_buy_currency[TASKS_TRADER] = {JASPER: TASKS_COIN}
    gd._task_coin_rewards = {"chicken": 1}  # C2 floor for funding-cycle calc
    gd._npc_locations[TASKS_TRADER] = TRADER_LOC
    # tasks_trader is NOT an event NPC (not in npc_event_codes)

    # Monster: cow drops cowhide (rate=100, min=1, max=1)
    gd._monster_level[COW] = 1
    gd._monster_drops[COW] = [(COWHIDE, 100, 1, 1)]
    gd._monster_locations[COW] = [COW_LOC]

    # Give cow harmless stats so is_winnable (predict_win) returns True
    # for a level-5 character with basic attack.
    gd._monster_hp[COW] = 10
    gd._monster_attack[COW] = {"air": 0}
    gd._monster_resistance[COW] = {}
    gd._monster_critical_strike[COW] = 0
    gd._monster_initiative[COW] = 0
    gd._monster_type[COW] = "normal"
    fill_monster_stat_defaults(gd)

    # Bank and gearcrafting workshop locations (needed by factory internals
    # but not required for is_plannable / relevant_actions calls).
    gd._bank_location = (0, 1)
    gd._workshop_locations["gearcrafting"] = (3, 0)
    gd._taskmaster_location = (0, 2)

    return gd


# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------

def _state_0coins():
    """Character has 0 tasks_coin — jasper_crystal is unaffordable."""
    return make_state(
        level=5,
        hp=100,
        max_hp=100,
        skills={"gearcrafting": 5},
        inventory={},
        x=0,
        y=0,
    )


def _state_8coins():
    """Character has 8 tasks_coin — jasper_crystal is affordable."""
    return make_state(
        level=5,
        hp=100,
        max_hp=100,
        skills={"gearcrafting": 5},
        inventory={TASKS_COIN: 8},
        x=0,
        y=0,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_satchel_unaffordable_is_not_plannable():
    """Regression guard for the 641K-node burn (C4 original bug).

    When the character holds 0 tasks_coin (jasper_crystal costs 8),
    GatherMaterialsGoal(satchel).is_plannable must return False.
    The affordability fast-fail (currency_afford_plannable_pure) detects
    that NpcBuy(jasper_crystal) is inapplicable and prunes immediately.
    No GOAP search should be attempted.
    """
    gd = _make_satchel_game_data()
    state = _state_0coins()
    goal = GatherMaterialsGoal(SATCHEL, {SATCHEL: 1})
    assert goal.is_plannable(state, gd) is False


def test_satchel_affordable_is_plannable_and_emits_npc_buy():
    """When the character holds >= 8 tasks_coin, the satchel is plannable
    and relevant_actions emits an NpcBuyAction for jasper_crystal.

    Two assertions:
    1. is_plannable returns True (affordability gate passes, skill gate passes).
    2. relevant_actions emits NpcBuyAction(item_code='jasper_crystal') so the
       planner can chain Fight(cow)×N -> NpcBuy(jasper_crystal) -> Craft(satchel).
    """
    gd = _make_satchel_game_data()
    state = _state_8coins()
    goal = GatherMaterialsGoal(SATCHEL, {SATCHEL: 1})

    # Assertion 1: plannable when affordable
    assert goal.is_plannable(state, gd) is True

    # Build a minimal action list (FightAction for cow; relevant_actions
    # will EMIT the NpcBuyAction based on the recipe closure).
    fight_cow = FightAction(monster_code=COW, locations=frozenset([COW_LOC]))
    actions = [fight_cow]

    kept = goal.relevant_actions(actions, state, gd)

    # Assertion 2: NpcBuyAction for jasper_crystal is emitted
    npc_buys = [a for a in kept if isinstance(a, NpcBuyAction) and a.item_code == JASPER]
    assert npc_buys, (
        f"expected NpcBuyAction(item_code={JASPER!r}) in relevant_actions output; "
        f"got: {kept}"
    )
    assert npc_buys[0].npc_code == TASKS_TRADER

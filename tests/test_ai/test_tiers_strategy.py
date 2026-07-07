from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality
from artifactsmmo_cli.ai.tiers.progression_tree import decide_tree
from artifactsmmo_cli.ai.tiers.strategy import (
    StrategyEngine,
    _producible,
    actionable_step,
    desired_state_of,
    is_reachable,
    root_category,
    root_cost,
    unmet_closure_size,
)
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   attack={"fire": 12}, crafting_skill="weaponcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"copper_dagger": {"copper_bar": 6}, "copper_bar": {"copper_ore": 10}}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    gd._monster_level = {"chicken": 1}
    fill_monster_stat_defaults(gd)
    return gd


def test_actionable_step_descends_to_ready_node():
    gd = _gd()
    step = actionable_step(ObtainItem("copper_dagger"), make_state(), gd)
    assert step == ObtainItem("copper_ore", 10)


def test_actionable_step_blocked_returns_none():
    gd = GameData()
    gd._crafting_recipes = {"a": {"a": 1}}  # self-referential, no gather/leaf path
    gd._item_stats = {"a": ItemStats(code="a", level=1, type_="resource")}
    assert actionable_step(ObtainItem("a"), make_state(), gd) is None


def test_unmet_closure_size_counts_unmet_nodes():
    gd = _gd()
    assert unmet_closure_size(ObtainItem("copper_dagger"), make_state(), gd) == 3
    assert unmet_closure_size(ObtainItem("copper_ore"), make_state(), gd) == 1


def test_root_category():
    assert root_category(ReachCharLevel(50)) == "char_level"
    assert root_category(ReachSkillLevel("mining", 50)) == "skills"
    assert root_category(ObtainItem("x")) == "gear"


def test_desired_state_of():
    assert desired_state_of(ObtainItem("copper_ore", 6)) == {"have": {"copper_ore": 6}}
    assert desired_state_of(ReachSkillLevel("mining", 7)) == {"skill": {"mining": 7}}
    assert desired_state_of(ReachCharLevel(12)) == {"level": 12}
    assert desired_state_of(None) == {}


def test_decide_delegates_to_the_progression_tree():
    """Phase 4b (THE FLIP): `StrategyEngine.decide` is a thin delegate to
    `decide_tree` — same state/game_data/objective yields the identical
    decision. The legacy ranking pipeline is deleted (Task 2)."""
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    eng = StrategyEngine(objective=obj, personality=BalancedPersonality())
    state = make_state(level=5, skills={"mining": 3})
    assert eng.decide(state, gd) == decide_tree(state, gd, obj)


def test_decide_forwards_band_adequate_and_step_servable():
    """The two live parameters pass through to `decide_tree` unchanged."""
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    eng = StrategyEngine(objective=obj, personality=BalancedPersonality())
    state = make_state(level=5, skills={"mining": 3})
    servable = lambda root, step: not isinstance(root, ObtainItem)  # noqa: E731
    assert eng.decide(state, gd, band_adequate=True, step_servable=servable) \
        == decide_tree(state, gd, obj, band_adequate=True, step_servable=servable)


def test_unmet_closure_size_dedups_shared_prereq():
    # X -> {A, B}; A -> {C}; B -> {C}: C is reached twice and deduped.
    gd = GameData()
    gd._crafting_recipes = {"X": {"A": 1, "B": 1}, "A": {"C": 1}, "B": {"C": 1}}
    gd._item_stats = {c: ItemStats(code=c, level=1, type_="resource") for c in "XABC"}
    assert unmet_closure_size(ObtainItem("X"), make_state(), gd) == 4  # X,A,B,C once each


def test_decide_skips_blocked_unmet_root():
    # A weapon whose only recipe is self-referential → its gear root is unmet
    # but has no actionable step, so decide skips it (the `step is None` path).
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    fill_monster_stat_defaults(gd)
    gd._item_stats = {"cursed_blade": ItemStats(code="cursed_blade", level=1, type_="weapon", attack={"f": 5})}
    gd._crafting_recipes = {"cursed_blade": {"cursed_blade": 1}}
    obj = CharacterObjective.from_game_data(gd)
    eng = StrategyEngine(obj, BalancedPersonality())
    d = eng.decide(make_state(level=5), gd)
    # the cursed_blade gear root is excluded from ranking (blocked)
    assert all("cursed_blade" not in rs.root_repr for rs in d.ranking)
    # but other roots (skills/level) still produce a decision
    assert d.chosen_root is not None


def test_root_cost_is_levels_remaining_for_leaf_goals():
    gd = _gd()
    assert root_cost(ReachSkillLevel("mining", 50), make_state(skills={"mining": 3}), gd) == 47
    assert root_cost(ReachCharLevel(50), make_state(level=3), gd) == 47
    assert root_cost(ReachSkillLevel("mining", 5), make_state(skills={"mining": 5}), gd) == 1  # floor


def test_root_cost_for_gear_uses_closure_size():
    gd = _gd()
    assert root_cost(ObtainItem("copper_dagger"), make_state(), gd) == 3


def test_rootscore_instrumental_always_false():
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    d = StrategyEngine(obj, BalancedPersonality()).decide(make_state(level=5), gd)
    assert all(rs.instrumental is False for rs in d.ranking)


def _reach_gd():
    gd = GameData()
    gd._item_stats = {
        "drop_blade": ItemStats(code="drop_blade", level=1, type_="weapon", attack={"f": 50}),
        "iron_helm": ItemStats(code="iron_helm", level=1, type_="helmet", resistance={"fire": 10},
                               crafting_skill="gearcrafting", crafting_level=1),
        "iron_bar": ItemStats(code="iron_bar", level=1, type_="resource"),
        "iron_ore": ItemStats(code="iron_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"iron_helm": {"iron_bar": 5}, "iron_bar": {"iron_ore": 3}}
    gd._resource_drops = {"iron_rocks": "iron_ore"}
    gd._resource_skill = {"iron_rocks": ("mining", 1)}
    gd._monster_level = {"chicken": 1}
    fill_monster_stat_defaults(gd)
    return gd


def test_producible():
    gd = _reach_gd()
    s = make_state(level=1)
    assert _producible("iron_helm", s, gd) is True   # craftable
    assert _producible("iron_ore", s, gd) is True     # gatherable (iron_rocks drops it)
    assert _producible("drop_blade", s, gd) is False   # no recipe, drop, or winnable monster


def test_is_reachable_gatherable_and_craftable_chain():
    gd = _reach_gd()
    s = make_state(level=1)
    assert is_reachable(ObtainItem("iron_ore"), s, gd) is True
    assert is_reachable(ObtainItem("iron_helm"), s, gd) is True


def test_is_reachable_false_for_unproducible_and_blocked_material():
    gd = _reach_gd()
    s = make_state(level=1)
    assert is_reachable(ObtainItem("drop_blade"), s, gd) is False
    gd._crafting_recipes["cursed_helm"] = {"drop_blade": 1}
    gd._item_stats["cursed_helm"] = ItemStats(code="cursed_helm", level=1, type_="helmet")
    assert is_reachable(ObtainItem("cursed_helm"), s, gd) is False


def test_is_reachable_skill_and_char_level():
    gd = _reach_gd()
    assert is_reachable(ReachSkillLevel("mining", 50), make_state(level=1), gd) is True
    # ReachCharLevel reachable because the player can beat a monster once it can
    # deal damage (combat_capable now uses predict_win, not a level margin).
    assert is_reachable(ReachCharLevel(50), make_state(level=1, attack={"fire": 10}), gd) is True


def test_is_reachable_char_level_false_when_underequipped_and_no_makeable_weapon():
    gd = GameData()
    gd._monster_level = {"dragon": 40}
    fill_monster_stat_defaults(gd)
    gd._item_stats = {"drop_blade": ItemStats(code="drop_blade", level=1, type_="weapon", attack={"f": 9})}
    assert is_reachable(ReachCharLevel(50), make_state(level=1), gd) is False


def test_is_reachable_satisfied_and_cycle():
    gd = _reach_gd()
    assert is_reachable(ReachCharLevel(1), make_state(level=5), gd) is True
    cyc = GameData()
    cyc._crafting_recipes = {"a": {"a": 1}}
    cyc._item_stats = {"a": ItemStats(code="a", level=1, type_="resource")}
    assert is_reachable(ObtainItem("a"), make_state(), cyc) is False


def test_actionable_step_none_for_unproducible_leaf():
    gd = _reach_gd()
    assert actionable_step(ObtainItem("drop_blade"), make_state(), gd) is None


def test_decide_skips_root_unreachable_in_current_game_data():
    # Objective built from data where iron_helm is craftable (attainable → targeted),
    # but decide() runs against game data lacking that production → the tree's
    # candidate pass finds no stats for it → the root is skipped.
    gd_full = _reach_gd()
    obj = CharacterObjective.from_game_data(gd_full)
    assert obj.target_gear.get("helmet_slot") == "iron_helm"
    gd_empty = GameData()
    gd_empty._monster_level = {"chicken": 1}  # char reachable; iron_helm not producible here
    fill_monster_stat_defaults(gd_empty)
    d = StrategyEngine(obj, BalancedPersonality()).decide(make_state(level=5), gd_empty)
    assert all("iron_helm" not in rs.root_repr for rs in d.ranking)


def test_unattainable_gear_not_targeted_but_craftable_is():
    gd = _reach_gd()  # drop_blade unattainable; iron_helm craftable-from-gatherables
    obj = CharacterObjective.from_game_data(gd)
    assert "weapon_slot" not in obj.target_gear           # drop_blade excluded at build
    assert obj.target_gear.get("helmet_slot") == "iron_helm"
    d = StrategyEngine(obj, BalancedPersonality()).decide(make_state(level=5), gd)
    reprs = [rs.root_repr for rs in d.ranking]
    assert any("iron_helm" in r for r in reprs)            # craftable gear is a candidate
    assert all("drop_blade" not in r for r in reprs)


def _combat_gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon",
                                crafting_skill="weaponcrafting", crafting_level=10,
                                attack={"fire": 20}),
        "iron_bar": ItemStats(code="iron_bar", level=10, type_="resource",
                              crafting_skill="mining", crafting_level=10),
        "iron_ore": ItemStats(code="iron_ore", level=10, type_="resource"),
        "iron_pickaxe": ItemStats(code="iron_pickaxe", level=10, type_="weapon",
                                  crafting_skill="weaponcrafting", crafting_level=10,
                                  skill_effects={"mining": 10}),
    }
    gd._crafting_recipes = {"iron_sword": {"iron_bar": 6}, "iron_pickaxe": {"iron_bar": 4},
                            "iron_bar": {"iron_ore": 1}}
    gd._resource_drops = {"iron_rocks": "iron_ore"}
    gd._resource_skill = {"iron_rocks": ("mining", 1)}
    return gd


def _combat_obj(gd: GameData) -> CharacterObjective:
    return CharacterObjective(
        target_char_level=50, target_skill_levels={},
        target_gear={"weapon_slot": "iron_sword"}, _game_data=gd,
        target_tools={"mining": "iron_pickaxe"})


def test_decide_returns_a_root_when_combat_capable():
    gd = _combat_gd()
    eng = StrategyEngine(_combat_obj(gd), BalancedPersonality())
    state = make_state(level=4, skills={"weaponcrafting": 1, "mining": 1})
    d = eng.decide(state, gd)
    assert d.chosen_root is not None


# --- C1: task-currency producibility ---

def test_producible_recognizes_task_earnable_currency():
    """tasks_coin is listed in task_reward_item_codes → _producible must
    return True without needing a recipe, resource-drop, or winnable fight."""
    gd = GameData()
    gd._task_reward_item_codes = frozenset({"tasks_coin"})
    assert _producible("tasks_coin", make_state(), gd) is True


def _gd_task_vendor() -> GameData:
    """jasper_crystal sold by a permanent, located tasks_trader NPC for tasks_coin
    (a task-earnable currency). No recipe, no gather/drop, no monster."""
    gd = GameData()
    gd._task_reward_item_codes = frozenset({"tasks_coin"})
    gd._npc_stock = {"tasks_trader": {"jasper_crystal": 8}}
    gd._npc_buy_currency = {"tasks_trader": {"jasper_crystal": "tasks_coin"}}
    gd._npc_locations = {"tasks_trader": (1, 2)}
    gd._item_stats = {
        "jasper_crystal": ItemStats(code="jasper_crystal", level=1, type_="resource"),
    }
    return gd


def test_producible_recognizes_currency_buy_with_task_earnable_currency():
    """jasper_crystal has no recipe, no resource-drop, and no winnable dropper;
    it is sold by a permanent vendor for tasks_coin (task-earnable) →
    _producible must return True (Finding A fix)."""
    gd = _gd_task_vendor()
    assert _producible("jasper_crystal", make_state(), gd) is True


def test_not_producible_for_currency_buy_with_unattainable_currency():
    """An NPC-sold item whose currency is neither gold nor task-earnable must
    NOT be producible — the flat currency check must not over-admit."""
    gd = GameData()
    gd._task_reward_item_codes = frozenset()
    gd._npc_stock = {"mystery_shop": {"rare_gem": 1}}
    gd._npc_buy_currency = {"mystery_shop": {"rare_gem": "void_token"}}  # not earnable
    gd._npc_locations = {"mystery_shop": (3, 3)}
    gd._item_stats = {"rare_gem": ItemStats(code="rare_gem", level=1, type_="resource")}
    assert _producible("rare_gem", make_state(), gd) is False

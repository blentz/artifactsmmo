import pytest

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ObtainItem, ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality
from artifactsmmo_cli.ai.tiers.progression_tree import decide_tree
from artifactsmmo_cli.ai.tiers.strategy import (
    StrategyEngine,
    _prereq_order,
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
        # A SEPARATE equippable (not the root itself) whose recipe consumes
        # copper_bar, so holding spare copies exercises the RECYCLE arm of
        # `ai/obtain_sources` without tripping the "root already owned" leaf
        # (holding spare copies of copper_dagger ITSELF would satisfy that
        # shortcut before the recipe/obtain_sources check is ever reached).
        "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                 crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"copper_dagger": {"copper_bar": 6}, "copper_bar": {"copper_ore": 10},
                           "copper_ring": {"copper_bar": 3}}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    gd._monster_level = {"chicken": 1}
    gd._workshop_locations = {"weaponcrafting": (1, 1)}
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


def test_actionable_step_stops_at_the_ready_source_material():
    """The live bug: actionable_step descended into copper_bar's recipe and
    returned ObtainItem(copper_ore, 10) -> 10 gathers, re-deriving from raw
    resources what recycling already covers. With copper_bar recoverable by
    recycling 2 held copper_ring (destroyable 1, capacity 1), it returns
    copper_bar itself."""
    gd = _gd()
    assert actionable_step(ObtainItem("copper_dagger"), make_state(), gd) \
        == ObtainItem("copper_ore", 10)
    state = make_state(inventory={"copper_ring": 2})
    assert actionable_step(ObtainItem("copper_dagger"), state, gd, NO_PROFILE_CONTEXT) \
        == ObtainItem("copper_bar", 6)


def test_is_reachable_agrees_with_the_descent_ready_source():
    """If the descent leafs a node (any ready non-craft `obtain_sources`
    route), reachability must not still descend its recipe — the two would
    disagree about the same node. `part`'s only recipe bottoms out in an
    unproducible raw material, so the chain is unreachable UNTIL `part` itself
    is recyclable from a held `part_source`, at which point reachability is
    governed by `part`'s OWN craftability, not its raw material's."""
    gd = GameData()
    gd._item_stats = {
        "trinket": ItemStats(code="trinket", level=1, type_="ring"),
        "part": ItemStats(code="part", level=1, type_="resource"),
        "raw_unobtainium": ItemStats(code="raw_unobtainium", level=1, type_="resource"),
        "part_source": ItemStats(code="part_source", level=1, type_="ring",
                                 crafting_skill="jewelrycrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"trinket": {"part": 5}, "part": {"raw_unobtainium": 2},
                           "part_source": {"part": 4}}
    gd._workshop_locations = {"jewelrycrafting": (1, 1)}
    state = make_state()
    assert is_reachable(ObtainItem("trinket"), state, gd) is False
    state2 = make_state(inventory={"part_source": 2})
    assert is_reachable(ObtainItem("trinket"), state2, gd, frozenset(),
                        NO_PROFILE_CONTEXT) is True


def test_unmet_closure_size_counts_unmet_nodes():
    gd = _gd()
    assert unmet_closure_size(ObtainItem("copper_dagger"), make_state(), gd) == 3
    assert unmet_closure_size(ObtainItem("copper_ore"), make_state(), gd) == 1


def test_unmet_closure_size_shrinks_with_a_ready_source():
    """A wired `ctx` must actually reach `prerequisites` inside the
    stack-extend loop: leafing copper_bar (2 held copper_ring) drops
    copper_ore from the closure (copper_dagger, copper_bar/6 — copper_ore's
    recipe is never descended), shrinking the count from 3 to 2. A regression
    that silently drops the forward (e.g. `prerequisites(node, state,
    game_data)` losing the trailing arg) would pass every OTHER test today but
    leave this one at 3."""
    gd = _gd()
    assert unmet_closure_size(ObtainItem("copper_dagger"), make_state(), gd) == 3
    state = make_state(inventory={"copper_ring": 2})
    assert unmet_closure_size(ObtainItem("copper_dagger"), state, gd,
                              NO_PROFILE_CONTEXT) == 2


def test_root_category():
    assert root_category(ReachCharLevel(50)) == "char_level"
    assert root_category(ObtainItem("x")) == "gear"


def test_desired_state_of():
    assert desired_state_of(ObtainItem("copper_ore", 6)) == {"have": {"copper_ore": 6}}
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


def test_root_cost_is_levels_remaining_for_char_level():
    gd = _gd()
    assert root_cost(ReachCharLevel(50), make_state(level=3), gd) == 47
    assert root_cost(ReachCharLevel(4), make_state(level=4), gd) == 1  # floor


def test_root_cost_for_gear_uses_closure_size():
    gd = _gd()
    assert root_cost(ObtainItem("copper_dagger"), make_state(), gd) == 3


def test_root_cost_shrinks_with_a_ready_source():
    """root_cost's ObtainItem branch delegates to unmet_closure_size — proving
    the `ctx` forward survives that delegation, not just the direct
    unmet_closure_size call. A regression dropping the trailing arg in
    `unmet_closure_size(root, state, game_data, ctx)` inside root_cost would
    leave the default-ctx tests green but this one stuck at 3."""
    gd = _gd()
    assert root_cost(ObtainItem("copper_dagger"), make_state(), gd) == 3
    state = make_state(inventory={"copper_ring": 2})
    assert root_cost(ObtainItem("copper_dagger"), state, gd, NO_PROFILE_CONTEXT) == 2


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


def test_is_reachable_char_level():
    gd = _reach_gd()
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


# --- Task 2: semantic (not repr) prerequisite order ---

def test_prereq_order_is_repr_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_prereq_order` ranks by prerequisite KIND (materials before char-level
    gates), never by `repr()`. Proven by forcing ObtainItem's repr to sort AFTER
    ReachCharLevel's — as an unrelated class/field rename could — and confirming
    the semantic order (materials first) is unaffected. Retires the
    `sorted(unmet, key=repr)` antipattern (feedback_no_alphabetical_tiebreak).
    (Skill-level prerequisite gates were retired in P3b — under-skill gear grinds
    via the LevelSkill action, not a tree-level skill node.)"""
    monkeypatch.setattr(ObtainItem, "__repr__", lambda self: f"Zzz({self.code})")
    obtain = ObtainItem("iron_ore", 5)
    char = ReachCharLevel(level=20)
    # Under the OLD `sorted(unmet, key=repr)` this renamed repr would now put
    # the char-level gate first ("ReachCharLevel..." < "Zzz(...)").
    assert repr(char) < repr(obtain)
    # Both remaining prerequisite KINDS ordered: materials (ObtainItem) before
    # char-level gates (ReachCharLevel), whatever the reprs. Covers _prereq_order's
    # ReachCharLevel arm directly.
    pair: list[MetaGoal] = [char, obtain]
    ordered = sorted(pair, key=_prereq_order)
    assert ordered == [obtain, char]  # semantic kind order, repr notwithstanding
    assert _prereq_order(char) == (1, "", 20)


def test_actionable_step_descends_to_material_for_underskill_craftable() -> None:
    """Integration-level pin: an under-skill craftable descends into its MATERIAL
    branch — the concrete, immediate thing the character can act on. The crafting
    skill is no longer emitted as a prerequisite node (P3b): under-skill gear
    grinds via UpgradeEquipmentGoal + the LevelSkill action, so actionable_step
    routes straight to the gatherable material."""
    gd = GameData()
    gd._item_stats = {
        "widget": ItemStats(code="widget", level=5, type_="ring",
                             crafting_skill="weaving", crafting_level=5),
        "thread": ItemStats(code="thread", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"widget": {"thread": 3}}
    gd._resource_drops = {"thread_patch": "thread"}
    gd._resource_skill = {"thread_patch": ("gathering", 1)}
    gd._monster_level = {"chicken": 1}
    fill_monster_stat_defaults(gd)
    state = make_state(level=5, skills={"weaving": 1})
    step = actionable_step(ObtainItem("widget"), state, gd)
    assert step == ObtainItem("thread", 3)


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

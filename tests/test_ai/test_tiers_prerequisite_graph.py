from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel
from artifactsmmo_cli.ai.tiers.prerequisite_graph import (
    best_attainable_weapon,
    combat_capable,
    prerequisites,
)
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   attack={"fire": 12}, crafting_skill="weaponcrafting", crafting_level=1),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon", attack={"fire": 30}),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"copper_dagger": {"copper_bar": 6}, "copper_bar": {"copper_ore": 10}}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    gd._monster_level = {"chicken": 1, "dragon": 40}
    gd._workshop_locations = {"weaponcrafting": (1, 1)}
    fill_monster_stat_defaults(gd)
    return gd


def test_obtain_craftable_yields_only_materials():
    # P3b: the crafting-skill gate is no longer emitted as a prerequisite node
    # (under-skill gear grinds via UpgradeEquipmentGoal + the LevelSkill action).
    # An ObtainItem's prereqs are just its material ObtainItems.
    gd = _gd()
    prereqs = prerequisites(ObtainItem("copper_dagger"), make_state(), gd)
    assert prereqs == [ObtainItem("copper_bar", 6)]


def test_obtain_already_owned_has_no_prereqs():
    gd = _gd()
    s = make_state(inventory={"copper_dagger": 1})
    assert prerequisites(ObtainItem("copper_dagger"), s, gd) == []


def test_obtain_already_equipped_is_satisfied_leaf():
    """An equippable already worn satisfies ObtainItem.is_satisfied, so the
    prereq descent short-circuits to an empty list (line 45-46)."""
    gd = _gd()
    s = make_state(equipment={"weapon_slot": "copper_dagger"})
    assert prerequisites(ObtainItem("copper_dagger"), s, gd) == []


def test_obtain_gatherable_is_leaf():
    # P3b: a gatherable (recipe-less) item is a leaf — no skill-gate prereq is
    # emitted; the material enters via the ObtainItem chain of its consumer.
    gd = _gd()
    assert prerequisites(ObtainItem("copper_ore"), make_state(), gd) == []


def test_obtain_unknown_source_is_leaf():
    gd = _gd()
    assert prerequisites(ObtainItem("mystery"), make_state(), gd) == []


def test_reach_char_level_leaf_when_combat_capable():
    gd = _gd()  # chicken (0 hp/atk stub) is stat-beatable once the player can hit
    state = make_state(level=1, attack={"fire": 10})
    assert prerequisites(ReachCharLevel(50), state, gd) == []


def test_reach_char_level_needs_weapon_when_underequipped():
    gd = GameData()
    gd._monster_level = {"dragon": 40}  # nothing beatable at level 1
    fill_monster_stat_defaults(gd)
    gd._item_stats = {"iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon", attack={"fire": 30})}
    prereqs = prerequisites(ReachCharLevel(50), make_state(level=1), gd)
    assert prereqs == [ObtainItem("iron_sword")]


def test_reach_char_level_leaf_when_no_weapon_exists():
    gd = GameData()
    gd._monster_level = {"dragon": 40}
    fill_monster_stat_defaults(gd)
    assert prerequisites(ReachCharLevel(50), make_state(level=1), gd) == []


def test_combat_capable_uses_stat_prediction_not_level_margin():
    gd = GameData()
    gd._monster_level = {"weak": 6, "tank": 6}
    gd._monster_hp = {"weak": 20, "tank": 100000}
    gd._monster_attack = {"weak": {}, "tank": {"fire": 5}}
    gd._monster_resistance = {"weak": {}, "tank": {}}
    gd._monster_critical_strike = {"weak": 0, "tank": 0}
    gd._monster_initiative = {"weak": 0, "tank": 0}
    armed = make_state(level=5, attack={"fire": 30}, initiative=50)
    # weak is killable with the player's attack; combat_capable -> True.
    assert combat_capable(armed, gd) is True
    # With no attack the player can't damage anything -> not combat-capable,
    # even though both monsters are within the old level+1 proxy.
    assert combat_capable(make_state(level=5), gd) is False


def test_best_attainable_weapon_highest_value_with_tiebreak():
    gd = _gd()
    assert best_attainable_weapon(gd) == "iron_sword"  # 30 > 12
    assert best_attainable_weapon(GameData()) is None   # no weapons


def test_a_material_with_a_ready_source_is_a_leaf():
    """copper_bar is craftable from 10 copper_ore, but recycling licensed
    surplus (2 held copper_dagger, whose recipe IS 6 copper_bar) yields a
    RECYCLE source directly — so it is directly actionable, not a recipe
    node. This is the whole epic: stop re-deriving from raw resources what a
    ready `ai/obtain_sources` route already covers."""
    gd = _gd()
    node = ObtainItem("copper_bar", 6)
    assert prerequisites(node, make_state(), gd) == [ObtainItem("copper_ore", 10)]
    state = make_state(inventory={"copper_dagger": 2})
    assert prerequisites(node, state, gd) == []


def test_leaf_rule_is_any_ready_source_not_fully_covering_the_need():
    """A ready source leafs the node even when its capacity does not cover the
    need (2 held copper_dagger -> 1 destroyable -> capacity 3, short of the 6
    needed): GOAP mixes recycle + gather to make up the shortfall (user
    decision)."""
    gd = _gd()
    state = make_state(inventory={"copper_dagger": 2})
    assert prerequisites(ObtainItem("copper_bar", 6), state, gd) == []


def test_no_destroyable_copies_still_descends():
    """Exactly 1 held copper_dagger is fully protected (COMBAT_WEAPON keeps
    the last copy) -> 0 destroyable -> no RECYCLE source, so the descent
    still falls into copper_bar's own recipe."""
    gd = _gd()
    state = make_state(inventory={"copper_dagger": 1})
    assert prerequisites(ObtainItem("copper_bar", 6), state, gd) \
        == [ObtainItem("copper_ore", 10)]


def test_exclude_recycle_leaf_descends_past_a_recycle_only_material():
    """A skill grind gathers its materials fresh — it does not recycle gear to
    source them (recycling gear is low-priority; the grind produces new
    material). With `exclude_recycle_leaf=True` a RECYCLE source no longer leafs
    a material, so copper_bar (whose only ready source is recycling the held
    copper_dagger) is NOT a leaf and the descent falls through to its gatherable
    raw, copper_ore. Default (grind flag off): copper_bar still leafs via the
    recycle source. copper_dagger/copper_bar mirror fire_staff/ash_plank."""
    gd = _gd()
    state = make_state(inventory={"copper_dagger": 2})
    assert prerequisites(ObtainItem("copper_bar", 6), state, gd) == []
    assert prerequisites(ObtainItem("copper_bar", 6), state, gd,
                         exclude_recycle_leaf=True) == [ObtainItem("copper_ore", 10)]


def test_exclude_recycle_leaf_still_leafs_a_junk_recycle():
    """The grind's value-aware flag skips only CURRENT-TIER gear recycle. A JUNK
    item (pursuit_value < RECYCLE_LEAF_VALUE_FLOOR) still leafs the material — a
    fast grind recovers surplus junk instead of gathering raw (2026-07-13
    behavior, preserved). rusty_scrap (attack 2 -> pursuit_value ~2000) recycles
    to copper_bar."""
    gd = _gd()
    gd._item_stats = {**gd._item_stats,
        "rusty_scrap": ItemStats(code="rusty_scrap", level=1, type_="weapon",
                                 attack={"fire": 2}, crafting_skill="weaponcrafting",
                                 crafting_level=1)}
    gd._crafting_recipes = {**gd._crafting_recipes, "rusty_scrap": {"copper_bar": 6}}
    state = make_state(inventory={"rusty_scrap": 2})
    assert prerequisites(ObtainItem("copper_bar", 6), state, gd,
                         exclude_recycle_leaf=True) == []


def test_gatherable_craftable_is_a_leaf_via_gather_source():
    """The ready-source leaf rule generalizes beyond RECYCLE (one-obtain-model
    epic, Task 5): a craftable item that is ALSO directly gatherable from a
    live resource tile is a leaf too — the descent never re-derives a raw
    material the character can just walk up and gather."""
    gd = GameData()
    gd._item_stats = {
        "iron_bar": ItemStats(code="iron_bar", level=1, type_="resource"),
        "iron_ore": ItemStats(code="iron_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"iron_bar": {"iron_ore": 3}}
    gd._resource_drops = {"iron_bar_vein": "iron_bar", "iron_rocks": "iron_ore"}
    gd._resource_skill = {"iron_bar_vein": ("mining", 1), "iron_rocks": ("mining", 1)}
    gd._resource_locations = {"iron_bar_vein": [(2, 2)], "iron_rocks": [(1, 1)]}
    assert prerequisites(ObtainItem("iron_bar"), make_state(), gd) == []


def test_cyclic_recipe_traversal_terminates():
    """prerequisites returns finite direct edges; a visited-set BFS over a
    cyclic recipe terminates (P2 adds no traversal; the test drives one)."""
    gd = GameData()
    gd._crafting_recipes = {"a": {"b": 1}, "b": {"a": 1}}
    gd._item_stats = {
        "a": ItemStats(code="a", level=1, type_="resource"),
        "b": ItemStats(code="b", level=1, type_="resource"),
    }
    seen = set()
    frontier = [ObtainItem("a")]
    while frontier:
        node = frontier.pop()
        if node in seen:
            continue
        seen.add(node)
        frontier.extend(prerequisites(node, make_state(), gd))
    assert ObtainItem("a", 1) in seen and ObtainItem("b", 1) in seen

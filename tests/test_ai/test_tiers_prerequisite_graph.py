from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.prerequisite_graph import (
    best_attainable_weapon,
    combat_capable,
    objective_roots,
    prerequisites,
)
from artifactsmmo_cli.ai.world_state import SKILL_NAMES
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
    fill_monster_stat_defaults(gd)
    return gd


def test_obtain_craftable_yields_skill_and_materials():
    gd = _gd()
    prereqs = prerequisites(ObtainItem("copper_dagger"), make_state(), gd)
    assert ReachSkillLevel("weaponcrafting", 1) in prereqs
    assert ObtainItem("copper_bar", 6) in prereqs


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


def test_obtain_gatherable_yields_gather_skill():
    gd = _gd()
    assert prerequisites(ObtainItem("copper_ore"), make_state(), gd) == [ReachSkillLevel("mining", 1)]


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


def test_reach_skill_level_is_leaf():
    assert prerequisites(ReachSkillLevel("mining", 30), make_state(), _gd()) == []


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


def test_objective_roots_cover_level_and_gear_but_never_skills():
    """Progression-tree Phase 4b Task 2: skills are pure prerequisites —
    objective_roots emits char-level and gear roots but NO standalone
    ReachSkillLevel root, with or without state."""
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    for roots in (objective_roots(obj),
                  objective_roots(obj, make_state(skills={s: 1 for s in SKILL_NAMES}))):
        assert ReachCharLevel(50) in roots
        assert any(isinstance(r, ObtainItem) for r in roots)  # gear targets
        assert not any(isinstance(r, ReachSkillLevel) for r in roots)


def test_objective_roots_adds_char_level_bootstrap_when_far_from_target():
    """Trace 2026-06-03/05: Robby last fought 2026-06-03T01:45 (dinged
    level 3), then ZERO fights across ~3300 cycles. Char xp stuck at
    6/350. Root cause: ReachCharLevel(50) effort=47 always lost ranking
    to small-effort gear chains; GrindCharacterXP never selected.

    Fix: when state.level + horizon < target_char_level, prepend a
    near-term ReachCharLevel(state.level + 2) root. Small effort (=2)
    competes with gear, gives GrindCharacterXP an actual chance to fire.
    Removed automatically when within the horizon."""
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    # Level 3 character — bootstrap should aim for level 5.
    state = make_state(level=3, skills={s: 1 for s in SKILL_NAMES})
    roots = objective_roots(obj, state)
    assert ReachCharLevel(5) in roots, (
        f"missing char-level bootstrap root at level 3; got {roots}"
    )
    # The long-haul target root must still exist.
    assert ReachCharLevel(obj.target_char_level) in roots


def test_objective_roots_omits_char_level_bootstrap_near_target():
    """Once horizon-overrun (state.level + horizon >= target), the
    bootstrap drops out — the long-haul ReachCharLevel(50) is now the
    near-term root anyway."""
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    # Bot at level 48, target 50: 48 + 2 = 50 >= 50 → no bootstrap.
    state = make_state(level=48, skills={s: 1 for s in SKILL_NAMES})
    roots = objective_roots(obj, state)
    char_roots = [r for r in roots if isinstance(r, ReachCharLevel)]
    assert ReachCharLevel(obj.target_char_level) in char_roots
    # Bootstrap target (level+2=50) coincides with long-haul → only one root.
    assert len(char_roots) == 1, (
        f"expected exactly the long-haul char-level root, got {char_roots}"
    )


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


def test_objective_roots_emits_tool_obtainitem_alongside_gear():
    """objective_roots must emit ObtainItem for every target_tools entry so
    the planner pursues skill tools (e.g. copper_pickaxe) the same way it
    pursues combat gear. Pre-fix: target_tools was empty and the bot mined
    forever without crafting a pickaxe (equip_value scored tools at 0)."""
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                  attack={"earth": 5}),
        "copper_pickaxe": ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                                   skill_effects={"mining": -1}),
    }
    gd._crafting_recipes = {c: {"bar": 1} for c in ("copper_dagger", "copper_pickaxe")}
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    obj = CharacterObjective.from_game_data(gd)
    roots = objective_roots(obj)
    # Combat target — slot-tagged (weapon → weapon_slot).
    assert ObtainItem("copper_dagger", slot="weapon_slot") in roots
    # Tool target — slot-less (tools rotate through weapon_slot per task).
    assert ObtainItem("copper_pickaxe") in roots


def _near_term_gd():
    gd = GameData()
    gd._item_stats = {
        "copper_armor": ItemStats(code="copper_armor", level=5, type_="body_armor",
                                  resistance={"earth": 6}),
        "dragon_armor": ItemStats(code="dragon_armor", level=40, type_="body_armor",
                                  resistance={"earth": 40}),
    }
    gd._crafting_recipes = {c: {"bar": 1} for c in ("copper_armor", "dragon_armor")}
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    return gd


def test_objective_roots_emits_near_term_gear_with_state():
    """With state supplied, the best usable-at-level upgrade per slot joins
    the root set alongside the (unreachable-at-low-level) BiS targets.
    Pre-fix trace 2026-06-11: no gear root survived is_reachable at level 6,
    so the gear category starved and armor slots stayed empty for 148
    fights."""
    obj = CharacterObjective.from_game_data(_near_term_gd())
    state = make_state(level=5)
    roots = objective_roots(obj, state)
    assert ObtainItem("copper_armor", slot="body_armor_slot") in roots   # near-term, usable now
    assert ObtainItem("dragon_armor", slot="body_armor_slot") in roots   # BiS stays


def test_objective_roots_dedupes_near_term_and_bis_overlap():
    """When the near-term pick IS the BiS item (high level), one root only."""
    gd = _near_term_gd()
    obj = CharacterObjective.from_game_data(gd)
    state = make_state(level=40)
    roots = objective_roots(obj, state)
    assert roots.count(ObtainItem("dragon_armor", slot="body_armor_slot")) == 1


def test_objective_roots_no_near_term_without_state():
    """Backward compat: stateless callers get no near-term roots."""
    obj = CharacterObjective.from_game_data(_near_term_gd())
    roots = objective_roots(obj)
    assert ObtainItem("copper_armor") not in roots


def test_gear_roots_are_slot_tagged_and_distinct_per_ring_slot():
    """Two ring slots both wanting copper_ring -> two DISTINCT slot-tagged
    gear roots (so ring2 isn't deduped/satisfied off ring1)."""
    gd = GameData()
    gd._item_stats = {"copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                               attack={"fire": 2})}
    gd._crafting_recipes = {"copper_ring": {"bar": 1}}
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    obj = CharacterObjective.from_game_data(gd)
    roots = objective_roots(obj)
    ring_roots = [r for r in roots
                  if isinstance(r, ObtainItem) and r.code == "copper_ring"]
    assert ObtainItem("copper_ring", slot="ring1_slot") in ring_roots
    assert ObtainItem("copper_ring", slot="ring2_slot") in ring_roots


def _gd_with_potions() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon", attack={"fire": 4}),
        "small_health_potion": ItemStats(code="small_health_potion", level=5,
            type_="utility", hp_restore=50, crafting_skill="alchemy", crafting_level=5),
        "enhanced_health_potion": ItemStats(code="enhanced_health_potion", level=45,
            type_="utility", hp_restore=300, crafting_skill="alchemy", crafting_level=45),
    }
    gd._crafting_recipes = {
        "copper_dagger": {"bar": 1},
        "small_health_potion": {"sunflower": 3},
        "enhanced_health_potion": {"sunflower": 3},
    }
    gd._resource_drops = {"rocks": "bar", "sunflower_field": "sunflower"}
    gd._resource_skill = {"rocks": ("mining", 1), "sunflower_field": ("alchemy", 1)}
    return gd


def test_objective_roots_emit_effect_based_potion_root():
    obj = CharacterObjective.from_game_data(_gd_with_potions())
    state = make_state(level=10, skills={**make_state().skills, "alchemy": 16})
    roots = objective_roots(obj, state)
    assert ObtainItem("small_health_potion", slot="utility1_slot") in roots
    assert ObtainItem("enhanced_health_potion", slot="utility1_slot") not in roots

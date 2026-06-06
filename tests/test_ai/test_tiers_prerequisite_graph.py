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


def test_objective_roots_cover_level_skills_gear():
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    roots = objective_roots(obj)
    assert ReachCharLevel(50) in roots
    assert all(ReachSkillLevel(s, 50) in roots for s in SKILL_NAMES)
    assert any(isinstance(r, ObtainItem) for r in roots)  # gear targets


def test_objective_roots_adds_craft_bootstrap_when_skill_at_floor():
    """Robby's level-3 trace 2026-06-04: weaponcrafting / gearcrafting /
    jewelrycrafting all sat at level 1 with 0 XP because the level-50
    ReachSkillLevel root has gap-50 effort and consistently lost ranking
    to small-effort gear chains. Those gear chains then stalled — copper
    recipes need weaponcrafting>=1 (technically met) but copper_dagger
    requires 6 copper_bar which itself needs mining XP; nothing forced a
    craft, so 951 gold and 1400 mining XP accumulated with zero gear
    progress.

    Fix: when a crafting skill is at the level-1 floor, objective_roots
    (with state) prepends ReachSkillLevel(skill, 5) — gap-4 effort, much
    more likely to win ranking and give LevelSkillGoal an actual cycle to
    fire."""
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    # Fresh character: all skills at the floor.
    state = make_state(skills={s: 1 for s in SKILL_NAMES})
    roots = objective_roots(obj, state)
    for skill in ("weaponcrafting", "gearcrafting", "jewelrycrafting"):
        assert ReachSkillLevel(skill, 5) in roots, (
            f"missing craft-bootstrap root for {skill}; got {roots}"
        )


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


def test_objective_roots_omits_craft_bootstrap_when_skill_above_floor():
    """Once a crafting skill is above the bootstrap target (>=5), the small
    bootstrap root drops out and the long-haul ReachSkillLevel(skill, 50)
    root takes over without competition from the bootstrap."""
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    state = make_state(skills={"weaponcrafting": 6, "gearcrafting": 5,
                                "jewelrycrafting": 1})
    roots = objective_roots(obj, state)
    assert ReachSkillLevel("weaponcrafting", 5) not in roots
    assert ReachSkillLevel("gearcrafting", 5) not in roots
    assert ReachSkillLevel("jewelrycrafting", 5) in roots  # still at floor


def test_objective_roots_backward_compat_without_state():
    """Legacy callers that don't pass state still get the original root
    set — no bootstrap roots, no regressions in old replay harnesses."""
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    roots = objective_roots(obj)
    # No bootstrap roots — only the canonical target=50 ReachSkillLevel.
    for skill in ("weaponcrafting", "gearcrafting", "jewelrycrafting"):
        assert ReachSkillLevel(skill, 5) not in roots
        assert ReachSkillLevel(skill, 50) in roots


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
    # Combat target.
    assert ObtainItem("copper_dagger") in roots
    # Tool target — the fix.
    assert ObtainItem("copper_pickaxe") in roots

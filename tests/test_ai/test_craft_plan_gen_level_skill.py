"""Task 4 of the LevelSkill epic (Phase 2): the directed craft generator
(`generate_next_craft_action`) emits a `LevelSkill` leg at the skill gate
instead of falling back to A* — one leg per cycle, mirroring the Fight
truncation. Still LIVE-INERT: `strategy_driver.py`'s is_plannable fast-fail
(retired in Task 5) prunes under-skill GatherMaterials goals BEFORE the
generator ever runs, so this changes no live behavior yet, only the
generator's own unit-level contract."""

from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.craft_plan_gen import generate_next_craft_action
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    """widget (gearcrafting lv5) / trinket (gearcrafting lv1), both made from
    gear_ore — a gatherable raw. Mirrors test_factory_level_skill.py's
    fixture, plus a resource-drop mapping so gear_ore is a gatherable ITEM
    (not just a leaf with no recipe): the CAN-GENERATE closure walk needs
    every non-craftable leaf to resolve as gatherable or dropped, else it
    returns None before ever reaching the skill gate for widget itself."""
    gd = GameData()
    gd._item_stats = {
        "widget": ItemStats(code="widget", level=5, type_="resource",
                            subtype="craft", crafting_skill="gearcrafting",
                            crafting_level=5),
        "trinket": ItemStats(code="trinket", level=1, type_="resource",
                             subtype="craft", crafting_skill="gearcrafting",
                             crafting_level=1),
        "gear_ore": ItemStats(code="gear_ore", level=1, type_="resource",
                              subtype="mob"),
    }
    gd._crafting_recipes = {"widget": {"gear_ore": 2}, "trinket": {"gear_ore": 1}}
    gd._resource_drops = {"gear_ore_rocks": "gear_ore"}
    gd._workshop_locations = {"gearcrafting": (2, 2)}
    gd._bank_location = (1, 1)
    gd._taskmaster_location = (0, 0)
    fill_monster_stat_defaults(gd)
    return gd


class TestDirectedGeneratorEmitsLevelSkillLeg:
    """Under-skill craft closure with a matching LevelSkill present in
    `actions` (Task 2's build_actions emits one per distinct craft level) →
    the generator returns [LevelSkill] instead of None (A* fallback)."""

    def test_returns_level_skill_leg_at_skill_gate(self) -> None:
        gd = _gd()
        state = make_state(inventory={}, bank_items={},
                           skills={"gearcrafting": 1})
        objective = CharacterObjective.from_game_data(gd)
        actions = build_actions(gd, state, objective, bank_accessible=True,
                                task_exchange_min_coins=0)
        goal = GatherMaterialsGoal("widget", {"widget": 1})

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result == [LevelSkill(skill="gearcrafting", target_level=5)], result

    def test_no_matching_level_skill_falls_back_to_none(self) -> None:
        """Regression guard for the pre-existing behavior: if no matching
        LevelSkill is present in `actions`, the generator still returns None
        (A* fallback), same as before this task."""
        gd = _gd()
        state = make_state(inventory={}, bank_items={},
                           skills={"gearcrafting": 1})
        goal = GatherMaterialsGoal("widget", {"widget": 1})
        # No LevelSkill in this hand-rolled list — build_actions is skipped.
        actions = [
            action for action in build_actions(
                gd, state, CharacterObjective.from_game_data(gd),
                bank_accessible=True, task_exchange_min_coins=0,
            )
            if not isinstance(action, LevelSkill)
        ]

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is None


def _gd_no_rung() -> GameData:
    """widget (gearcrafting lv5) made from gear_ore (a gatherable raw), but NO
    in-level gearcrafting grind rung: widget itself is the only gearcrafting
    recipe and it is above the character's current level, so
    `skill_grind_target(gearcrafting, ...)` returns None → the LevelSkill
    build_actions emits is present-but-NOT-applicable. Fix A must gate the emit
    on `is_applicable` and fall back to A* (None), never emit the dead rung."""
    gd = GameData()
    gd._item_stats = {
        "widget": ItemStats(code="widget", level=5, type_="resource",
                            subtype="craft", crafting_skill="gearcrafting",
                            crafting_level=5),
        "gear_ore": ItemStats(code="gear_ore", level=1, type_="resource",
                              subtype="mob"),
    }
    gd._crafting_recipes = {"widget": {"gear_ore": 2}}
    gd._resource_drops = {"gear_ore_rocks": "gear_ore"}
    gd._workshop_locations = {"gearcrafting": (2, 2)}
    gd._bank_location = (1, 1)
    gd._taskmaster_location = (0, 0)
    fill_monster_stat_defaults(gd)
    return gd


class TestDirectedGeneratorGatesLevelSkillOnApplicable:
    """Fix A: the matching LevelSkill is present in `actions` but its
    `is_applicable` is False (no obtainable in-level grind rung) → the
    generator must fall back to A* (None), NOT emit the inapplicable rung
    (which, at execution, would hit the grind dead-end guard)."""

    def test_inapplicable_level_skill_falls_back_to_none(self) -> None:
        gd = _gd_no_rung()
        state = make_state(inventory={}, bank_items={},
                           skills={"gearcrafting": 1})
        objective = CharacterObjective.from_game_data(gd)
        actions = build_actions(gd, state, objective, bank_accessible=True,
                                task_exchange_min_coins=0)
        # Sanity: build_actions DID emit the (now-inapplicable) LevelSkill, so
        # this test exercises the is_applicable gate, not a missing-action path.
        lvl = next(a for a in actions if isinstance(a, LevelSkill))
        assert lvl == LevelSkill(skill="gearcrafting", target_level=5)
        assert lvl.is_applicable(state, gd) is False
        goal = GatherMaterialsGoal("widget", {"widget": 1})

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is None, result

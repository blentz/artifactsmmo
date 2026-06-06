"""Tests for LevelSkillGoal (Phase G-E)."""

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.level_skill import (
    MAX_SKILL_GAP,
    PRIORITY_WHEN_FIRING,
    LevelSkillGoal,
)
from artifactsmmo_cli.ai.learning.skill_xp_curve import SkillXpCurve
from artifactsmmo_cli.ai.planner import GOAPPlanner
from tests.test_ai.fixtures import make_state


def _gd_with_weapon_recipes() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        ),
        "iron_dagger": ItemStats(
            code="iron_dagger", level=10, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=10,
        ),
        "copper_bar": ItemStats(
            code="copper_bar", level=1, type_="resource",
            crafting_skill="mining", crafting_level=1,
        ),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "iron_bar": ItemStats(
            code="iron_bar", level=10, type_="resource",
            crafting_skill="mining", crafting_level=10,
        ),
        "iron_ore": ItemStats(code="iron_ore", level=10, type_="resource"),
    }
    gd._crafting_recipes = {
        "copper_dagger": {"copper_bar": 6},
        "iron_dagger": {"iron_bar": 6},
        # Recipe-closure walk: dagger ← bar ← ore (gather). Registering the
        # intermediate recipes + resource drops lets LevelSkillGoal's tightened
        # relevant_actions filter see copper_rocks as in-closure for
        # weaponcrafting.
        "copper_bar": {"copper_ore": 1},
        "iron_bar": {"iron_ore": 1},
    }
    gd._resource_drops = {"copper_rocks": "copper_ore", "iron_rocks": "iron_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1), "iron_rocks": ("mining", 10)}
    return gd


class TestPriority:
    def test_zero_when_already_at_target(self):
        goal = LevelSkillGoal("weaponcrafting", 3)
        state = make_state(skills={"weaponcrafting": 3})
        assert goal.value(state, _gd_with_weapon_recipes()) == 0.0

    def test_zero_when_gap_too_large(self):
        goal = LevelSkillGoal("weaponcrafting", 1 + MAX_SKILL_GAP + 1)
        state = make_state(skills={"weaponcrafting": 1})
        assert goal.value(state, _gd_with_weapon_recipes()) == 0.0

    def test_fires_with_small_gap_and_craftable(self):
        goal = LevelSkillGoal("weaponcrafting", 3)
        state = make_state(skills={"weaponcrafting": 1})
        assert goal.value(state, _gd_with_weapon_recipes()) == PRIORITY_WHEN_FIRING

    def test_zero_when_no_craftable_in_skill(self):
        """Skill exists but no recipe at current skill level → grinding impossible."""
        goal = LevelSkillGoal("weaponcrafting", 3)
        state = make_state(skills={"weaponcrafting": 0})  # below copper_dagger's level 1
        assert goal.value(state, _gd_with_weapon_recipes()) == 0.0


class TestSatisfaction:
    def test_satisfied_at_target(self):
        goal = LevelSkillGoal("weaponcrafting", 3)
        assert goal.is_satisfied(make_state(skills={"weaponcrafting": 3})) is True

    def test_satisfied_above_target(self):
        goal = LevelSkillGoal("weaponcrafting", 3)
        assert goal.is_satisfied(make_state(skills={"weaponcrafting": 5})) is True

    def test_unsatisfied_below_target(self):
        goal = LevelSkillGoal("weaponcrafting", 3)
        assert goal.is_satisfied(make_state(skills={"weaponcrafting": 2})) is False

    def test_skill_xp_does_not_satisfy_below_target(self):
        """ApplyBaseline contract: skill_xp is a server-snapshot baseline field.
        is_satisfied no longer triggers off skill_xp — only the skills level matters.
        Prior to the contract fix, skill_xp was the planner-sim sentinel; gather/craft
        deliberately mutated it. Post-fix, only skills[skill] >= target satisfies."""
        goal = LevelSkillGoal("weaponcrafting", 50, initial_skill_xp=0)
        state = make_state(skills={"weaponcrafting": 1}, skill_xp={"weaponcrafting": 5})
        assert goal.is_satisfied(state) is False

    def test_unsatisfied_when_level_below_target(self):
        """is_satisfied returns False when skills[skill] < target."""
        goal = LevelSkillGoal("weaponcrafting", 50, initial_skill_xp=10)
        state = make_state(skills={"weaponcrafting": 1}, skill_xp={"weaponcrafting": 10})
        assert goal.is_satisfied(state) is False

    def test_satisfied_when_level_at_target_regardless_of_xp(self):
        """is_satisfied returns True when skills[skill] >= target, even if initial_skill_xp set."""
        goal = LevelSkillGoal("weaponcrafting", 5, initial_skill_xp=999)
        state = make_state(skills={"weaponcrafting": 5}, skill_xp={"weaponcrafting": 999})
        assert goal.is_satisfied(state) is True

    def test_satisfied_by_projected_xp_progress(self):
        """With a learned SkillXpCurve, the projected XP delta (mutated by
        Gather/Craft.apply) can cross the required threshold so the planner
        sees the goal as plannable-satisfiable."""
        # Curve: at current_level=1, 100 XP needed to reach level 2.
        curve = SkillXpCurve(observed={1: 100})
        goal = LevelSkillGoal("alchemy", target_level=2, xp_curve=curve)
        state = make_state(
            skills={"alchemy": 1},
            skill_xp={"alchemy": 50},
            projected_skill_xp_delta={"alchemy": 60},  # 50 + 60 >= 100
        )
        assert goal.is_satisfied(state) is True

    def test_unsatisfied_when_projected_below_required(self):
        """Projected delta + current XP below the curve threshold → not satisfied."""
        curve = SkillXpCurve(observed={1: 100})
        goal = LevelSkillGoal("alchemy", target_level=2, xp_curve=curve)
        state = make_state(
            skills={"alchemy": 1},
            skill_xp={"alchemy": 10},
            projected_skill_xp_delta={"alchemy": 5},  # 15 < 100
        )
        assert goal.is_satisfied(state) is False

    def test_unsatisfied_when_no_curve_and_level_below(self):
        """Default empty curve → projection path disabled; only the skills
        snapshot path can satisfy. Below-target stays unsatisfied even with a
        huge projected delta."""
        goal = LevelSkillGoal("alchemy", target_level=2)
        state = make_state(
            skills={"alchemy": 1},
            skill_xp={"alchemy": 99999},
            projected_skill_xp_delta={"alchemy": 99999},
        )
        assert goal.is_satisfied(state) is False


class TestRelevantActions:
    def test_includes_craft_in_skill_family(self):
        goal = LevelSkillGoal("weaponcrafting", 3)
        gd = _gd_with_weapon_recipes()
        actions = [
            RestAction(),
            CraftAction(code="copper_dagger", quantity=1),
            CraftAction(code="ash_plank", quantity=1),  # different skill
            GatherAction(resource_code="copper_rocks"),
        ]
        relevant = goal.relevant_actions(actions, make_state(), gd)
        codes = [a.code if isinstance(a, CraftAction) else None for a in relevant]
        assert "copper_dagger" in codes
        assert "ash_plank" not in codes
        assert any(isinstance(a, RestAction) for a in relevant)
        assert any(isinstance(a, GatherAction) for a in relevant)

    def test_excludes_gathers_outside_skill_recipe_closure(self):
        """Trace 2026-06-05 (cycles 80/120/300):
        LevelSkill(weaponcrafting->5) timed out at 90s with ~250k nodes
        because the relevant_actions filter accepted EVERY gather as
        'fair game'. With the closure-bound filter, only gathers whose
        drop is in a weaponcrafting recipe input survive."""
        goal = LevelSkillGoal("weaponcrafting", 3)
        gd = _gd_with_weapon_recipes()
        # ash_tree drops ash_wood -> NOT in any weaponcrafting recipe
        # closure (those recipes use copper_bar -> copper_ore -> copper_rocks).
        gd._resource_drops["ash_tree"] = "ash_wood"
        gd._resource_skill["ash_tree"] = ("woodcutting", 1)
        actions = [
            GatherAction(resource_code="copper_rocks"),  # in-closure
            GatherAction(resource_code="ash_tree"),       # OUT of closure
        ]
        relevant = goal.relevant_actions(actions, make_state(), gd)
        resources = {a.resource_code for a in relevant if isinstance(a, GatherAction)}
        assert "copper_rocks" in resources
        assert "ash_tree" not in resources, (
            "ash_tree drops ash_wood — not a weaponcrafting recipe input — "
            "should be filtered out to keep planner branching bounded"
        )

    def test_skips_in_skill_item_with_empty_recipe(self):
        """An in-skill craftable registered with an EMPTY recipe dict yields no
        material closure, so it's skipped (line 119-120) and contributes no
        gather/withdraw actions — only the real copper_dagger chain survives."""
        goal = LevelSkillGoal("weaponcrafting", 3)
        gd = _gd_with_weapon_recipes()
        # A weaponcrafting item whose recipe is registered but empty.
        gd._item_stats["mystery_blade"] = ItemStats(
            code="mystery_blade", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        gd._crafting_recipes["mystery_blade"] = {}
        actions = [
            CraftAction(code="copper_dagger", quantity=1),
            CraftAction(code="mystery_blade", quantity=1),
            GatherAction(resource_code="copper_rocks"),
        ]
        relevant = goal.relevant_actions(actions, make_state(), gd)
        craft_codes = {a.code for a in relevant if isinstance(a, CraftAction)}
        # mystery_blade still passes the craft-family filter (it IS in-skill)
        # but contributes nothing to the gather closure.
        assert "copper_dagger" in craft_codes
        gather_res = {a.resource_code for a in relevant if isinstance(a, GatherAction)}
        assert gather_res == {"copper_rocks"}

    def test_excludes_crafts_and_closure_above_current_skill_level(self):
        """Only recipes craftable AT the character's current skill give XP, so
        only THEIR closure should reach the planner. weaponcrafting@2 can craft
        copper_dagger (level 1) but NOT iron_dagger (level 10); the iron chain
        (iron_bar->iron_ore->iron_rocks) must be excluded or it re-inflates the
        branching factor back to the 505k-node / 90s timeout this filter exists
        to prevent (Robby weaponcrafting@2 regression)."""
        goal = LevelSkillGoal("weaponcrafting", 5)
        gd = _gd_with_weapon_recipes()
        state = make_state(skills={"weaponcrafting": 2})
        actions = [
            CraftAction(code="copper_dagger", quantity=1),   # craft level 1 <= 2: keep
            CraftAction(code="iron_dagger", quantity=1),      # craft level 10 > 2: drop
            GatherAction(resource_code="copper_rocks"),        # copper chain: keep
            GatherAction(resource_code="iron_rocks"),          # iron chain: drop
        ]
        relevant = goal.relevant_actions(actions, state, gd)
        craft_codes = {a.code for a in relevant if isinstance(a, CraftAction)}
        gather_res = {a.resource_code for a in relevant if isinstance(a, GatherAction)}
        assert craft_codes == {"copper_dagger"}
        assert gather_res == {"copper_rocks"}, (
            "iron_rocks feeds only iron_dagger (craft level 10), uncraftable at "
            "weaponcrafting 2 — it must not be in the relevant-action closure"
        )

    def test_withdraw_filtered_to_recipe_inputs(self):
        """Symmetric to the gather restriction: only withdraws of items in
        the skill's recipe closure (leaves + intermediates + in-skill
        items themselves) are relevant."""
        goal = LevelSkillGoal("weaponcrafting", 3)
        gd = _gd_with_weapon_recipes()
        actions = [
            WithdrawItemAction(code="copper_ore", quantity=1, bank_location=(4, 0)),
            WithdrawItemAction(code="copper_bar", quantity=1, bank_location=(4, 0)),
            WithdrawItemAction(code="copper_dagger", quantity=1, bank_location=(4, 0)),
            WithdrawItemAction(code="ash_wood", quantity=1, bank_location=(4, 0)),
        ]
        relevant = goal.relevant_actions(actions, make_state(), gd)
        codes = {a.code for a in relevant if isinstance(a, WithdrawItemAction)}
        assert codes == {"copper_ore", "copper_bar", "copper_dagger"}


class TestRepr:
    def test_repr_includes_skill_and_target(self):
        assert repr(LevelSkillGoal("woodcutting", 5)) == "LevelSkill(woodcutting->5)"


def _gd_with_alchemy_resource() -> GameData:
    """GameData with an alchemy-skill resource so GatherAction bumps alchemy skill_xp."""
    gd = GameData()
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_drops = {"sunflower_field": "sunflower"}
    gd._resource_skill = {"sunflower_field": ("alchemy", 1)}
    gd._resource_locations = {"sunflower_field": [(3, 0)]}
    gd._workshop_locations = {}
    gd._monster_locations = {}
    gd._monster_level = {}
    gd._bank_location = (4, 0)
    return gd


class TestPlannerIntegration:
    """Decisive integration test: proves the skill goal is now plannable (was: 646k nodes / timeout)."""

    def test_level_skill_goal_satisfied_when_skills_reaches_target(self):
        """ApplyBaseline contract: skill_xp is a server-snapshot baseline field that
        Action.apply MUST preserve. LevelSkillGoal therefore is_satisfied SOLELY on
        skills[skill] >= target. The planner cannot simulate skill-level advancement
        (no action mutates `skills`), so satisfaction is observed only after a real
        API call advances state.skills via WorldState.from_character_schema."""
        gd = _gd_with_alchemy_resource()
        # Already-satisfied: skills meets target, plan is empty.
        already_state = make_state(
            skills={"alchemy": 2}, skill_xp={"alchemy": 0},
            hp=150, max_hp=150, inventory={}, inventory_max=20, x=0, y=0,
        )
        goal = LevelSkillGoal("alchemy", target_level=2, initial_skill_xp=0)
        assert goal.is_satisfied(already_state) is True

        # Not-yet-satisfied: skills below target. Gather no longer simulates skill
        # advancement (the planner-sim sentinel was the bug). The goal correctly
        # reports unsatisfied for the pre-API state.
        below_state = make_state(
            skills={"alchemy": 1}, skill_xp={"alchemy": 0},
            hp=150, max_hp=150, inventory={}, inventory_max=20, x=0, y=0,
        )
        assert goal.is_satisfied(below_state) is False

"""E2E guard: at L8/alchemy-2 with sunflowers held, the potion root's
ReachSkillLevel(alchemy,5) step is now SERVABLE via the NO_GRIND→gather branch.

Scenario: the alchemy skill has no craftable item below L5, so
skill_step_dispatch_pure returns NO_GRIND.  Task 2 added the gatherable-skill
fallback in objective_step_goal: best_gather_resource_drop("alchemy", 2, gd)
returns "sunflower" (sunflower_field is alchemy L1), so objective_step_goal
returns GatherMaterialsGoal(target_item="sunflower") instead of None.

Without the Task 2 fix, objective_step_goal returned None here, marking the
potion root (ObtainItem(small_health_potion, utility1_slot)) UNSERVABLE and
causing keep_servable to drop it from the strategy ranking.

Layer asserted: objective_step_goal directly — the exact predicate that
_step_servable (player.py:1591) calls.  Testing at this layer avoids live-API
dependencies while covering the only decision point keep_servable relies on.
"""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachSkillLevel
from tests.test_ai.fixtures import make_state


def _alchemy_gd() -> GameData:
    """Minimal GameData for the L8/alchemy-2 alchemy-bootstrap scenario.

    small_health_potion: alchemy craft L5, recipe sunflower×3.
    sunflower_field: alchemy L1 resource that drops sunflower.
    No alchemy-craftable item at or below L2 → skill_step_dispatch → NO_GRIND.
    """
    gd = GameData()
    gd._item_stats = {
        "small_health_potion": ItemStats(
            code="small_health_potion", level=5, type_="utility",
            hp_restore=30, crafting_skill="alchemy", crafting_level=5,
        ),
    }
    gd._crafting_recipes = {"small_health_potion": {"sunflower": 3}}
    gd._resource_skill = {"sunflower_field": ("alchemy", 1)}
    gd._resource_drops = {"sunflower_field": "sunflower"}
    return gd


def _ctx() -> SelectionContext:
    return SelectionContext(
        bank_accessible=True,
        bank_required_level=0,
        bank_unlock_monster=None,
        initial_xp=0,
        task_exchange_min_coins=1,
        combat_monster=None,
        gear_review_active=False,
    )


class TestAlchemyBootstrapServability:
    """Reproduce the L8/alchemy-2 live bug and assert the Task 2 fix holds.

    The bug: at L8/alchemy-2 with ≥3 sunflowers, the potion root's
    ReachSkillLevel(alchemy,5) step dispatched to NO_GRIND (no alchemy item
    craftable at L2), objective_step_goal returned None, _step_servable returned
    False, and keep_servable dropped the potion root from the ranking.

    The fix (Task 2): the NO_GRIND branch now checks best_gather_resource_drop;
    for a gatherable skill (alchemy: sunflower_field at L1) it returns a
    GatherMaterialsGoal so the step is servable and the potion root survives.
    """

    def _scenario_state(self):
        return make_state(
            level=8,
            skills={"alchemy": 2},
            inventory={"sunflower": 3},
        )

    def test_reach_skill_level_alchemy_step_is_servable(self):
        """objective_step_goal returns GatherMaterialsGoal for
        ReachSkillLevel(alchemy,5) at alchemy 2 — the NO_GRIND gatherable-skill
        fallback introduced by Task 2.

        Without the fix: objective_step_goal returned None here, the potion root
        was UNSERVABLE, and keep_servable dropped it from the strategy ranking.
        """
        gd = _alchemy_gd()
        state = self._scenario_state()
        step = ReachSkillLevel(skill="alchemy", level=5)
        root = ObtainItem(code="small_health_potion", quantity=1, slot="utility1_slot")

        goal = objective_step_goal(step, state, gd, _ctx(), root=root)

        assert isinstance(goal, GatherMaterialsGoal), (
            "objective_step_goal must return GatherMaterialsGoal for alchemy NO_GRIND "
            f"(gatherable skill); got {goal!r} — None means the potion root is "
            "unservable and keep_servable would drop it from the ranking"
        )
        assert "sunflower" in goal.needed, (
            f"gather needed map must target 'sunflower' (sunflower_field drop), "
            f"got needed={goal.needed!r}"
        )

    def test_gather_demand_is_held_plus_one(self):
        """needed quantity == held_sunflowers + 1 (grind-one-replan pattern).

        state holds 3 sunflowers → needed{"sunflower": 4}.
        """
        gd = _alchemy_gd()
        state = self._scenario_state()
        step = ReachSkillLevel(skill="alchemy", level=5)
        root = ObtainItem(code="small_health_potion", quantity=1, slot="utility1_slot")

        goal = objective_step_goal(step, state, gd, _ctx(), root=root)

        assert isinstance(goal, GatherMaterialsGoal)
        assert goal.needed == {"sunflower": 4}, (
            "needed must be held(3) + 1 = 4 (grind-one-replan); "
            f"got {goal.needed!r}"
        )

    def test_non_gatherable_skill_still_returns_none(self):
        """A skill with NO gather resource returns None after the fix.

        cooking is not a gatherable skill (no resource_skill entry in gd) so
        the gatherable-skill fallback does not fire and objective_step_goal
        returns None — only the gatherable path gains a goal.
        """
        gd = _alchemy_gd()  # no cooking resource in this gd
        state = make_state(level=8, skills={"cooking": 2})
        step = ReachSkillLevel(skill="cooking", level=5)

        goal = objective_step_goal(step, state, gd, _ctx())

        assert goal is None, (
            "non-gatherable skill (cooking has no resource) must still return None; "
            f"got {goal!r}"
        )

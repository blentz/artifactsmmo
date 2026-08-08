"""The reprs the yield history is keyed by.

A repr is a contract between the cycle writer and every reader that aggregates
over it, and breaking it is silent: a reader asking for a repr nobody emits gets
an empty result, indistinguishable from a cold start. `8c812fb3` broke exactly
that contract for ~2.5 months.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.learning.yield_reprs import (
    TASKMASTER_ITEMS,
    TASKMASTER_MONSTERS,
    grind_xp_repr,
    grind_xp_repr_prefix,
    task_pursuit_code,
    task_pursuit_reprs_for,
    taskmaster_for_item,
)


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource",
                               crafting_skill="woodcutting", crafting_level=1),
        "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
        "wolf_hair": ItemStats(code="wolf_hair", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"ash_plank": {"ash_wood": 1}}
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._resource_drops_full = {"ash_tree": [("ash_wood", 100, 1, 1)]}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    return gd


class TestGrindRepr:
    def test_matches_the_goal_that_actually_writes_it(self):
        """`GrindCharacterXPGoal.__repr__` is `GrindCharacterXP(<monster>)`. If
        these ever diverge the learned-rate lookups go quiet, which is precisely
        the failure this module exists to prevent."""
        assert grind_xp_repr("red_slime") == repr(GrindCharacterXPGoal("red_slime"))

    def test_prefix_matches_its_own_reprs(self):
        assert grind_xp_repr("chicken").startswith(grind_xp_repr_prefix())


class TestTaskmasterForItem:
    def test_craftable_item_belongs_to_the_items_master(self):
        assert taskmaster_for_item("ash_plank", _gd()) == TASKMASTER_ITEMS

    def test_gathered_item_belongs_to_the_items_master(self):
        """Gathered counts as having a producing skill — the resource's own
        gather skill — so it is an items task, not a monster hunt."""
        assert taskmaster_for_item("ash_wood", _gd()) == TASKMASTER_ITEMS

    def test_drop_only_item_belongs_to_the_monsters_master(self):
        """No producing skill means the only source is a monster drop, so the
        skill related to it is combat."""
        assert taskmaster_for_item("wolf_hair", _gd()) == TASKMASTER_MONSTERS


class TestTaskPursuitCode:
    def test_extracts_the_task_code(self):
        assert task_pursuit_code("PursueTask(copper_ore)") == "copper_ore"

    def test_rejects_a_different_goal(self):
        assert task_pursuit_code("GrindCharacterXP(chicken)") is None
        assert task_pursuit_code("CraftPotionsGoal") is None

    def test_rejects_an_unterminated_repr(self):
        assert task_pursuit_code("PursueTask(copper_ore") is None

    def test_empty_code_is_not_a_task(self):
        """`PursueTask()` names no item, so it cannot be assigned a taskmaster —
        None rather than an empty code that `taskmaster_for_item` would then have
        to judge."""
        assert task_pursuit_code("PursueTask()") is None


class TestTaskPursuitGrouping:
    def test_groups_by_taskmaster_not_by_task_code(self):
        """The grain that makes the low-yield comparison possible: per-task-code
        would leave every freshly-issued task reading cold."""
        gd = _gd()
        observed = ["PursueTask(ash_plank)", "PursueTask(ash_wood)",
                    "PursueTask(wolf_hair)", "GrindCharacterXP(wolf)"]
        assert task_pursuit_reprs_for(TASKMASTER_ITEMS, observed, gd) == [
            "PursueTask(ash_plank)", "PursueTask(ash_wood)"]
        assert task_pursuit_reprs_for(TASKMASTER_MONSTERS, observed, gd) == [
            "PursueTask(wolf_hair)"]

    def test_ignores_non_task_reprs(self):
        assert task_pursuit_reprs_for(
            TASKMASTER_ITEMS, ["GrindCharacterXP(chicken)", "RestoreHP"], _gd()) == []

    def test_empty_history_groups_to_nothing(self):
        assert task_pursuit_reprs_for(TASKMASTER_ITEMS, [], _gd()) == []

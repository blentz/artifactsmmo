"""Behavior tests closing coverage gaps in documented blockers, inventory
caps, and GameData recursion guards / lookup helpers."""

from artifactsmmo_cli.ai.blockers import BlockerRegistry, seed_documented_blockers
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.inventory_caps import overstocked_items
from tests.test_ai.fixtures import make_state


class TestDocumentedBlockerSkipsUnknownMonsterLevel:
    def test_monster_with_nonpositive_level_is_not_a_combat_gate(self):
        """A monster whose level is unknown (<=0) produces no combat blocker
        (line 49 continue); a real over-level monster still does."""
        gd = GameData()
        gd._monster_level = {"ghost": 0, "yellow_slime": 4}
        reg = BlockerRegistry()
        state = make_state(level=1, skills={})
        added = seed_documented_blockers(reg, gd, state)
        assert "fight:ghost" not in reg.blockers
        assert "fight:yellow_slime" in reg.blockers
        assert added == 1


class TestOverstockSkipsZeroQty:
    def test_zero_quantity_inventory_entry_is_skipped(self):
        """An inventory entry at qty 0 never counts as overstock (line 94);
        a real over-cap item does."""
        gd = GameData()
        gd._item_stats = {"junk": ItemStats(code="junk", level=1, type_="resource")}
        gd._crafting_recipes = {}
        state = make_state(inventory={"phantom": 0, "junk": 7})
        excess = overstocked_items(state, gd)
        assert "phantom" not in excess
        # junk has no recipe/task use -> cap 0 -> all 7 overstocked.
        assert excess["junk"] == 7


class TestMaxRecipeDemandCycleGuard:
    def test_recursive_recipe_cycle_terminates(self):
        """A cyclic recipe graph (a needs b, b needs a) must not infinite-loop;
        the visited guard (line 137) caps the recursion and returns a finite
        demand."""
        gd = GameData()
        gd._crafting_recipes = {
            "alpha": {"beta": 2},
            "beta": {"alpha": 3},
        }
        # Should return without hanging; demand is a finite positive number.
        demand = gd.max_recipe_demand("alpha")
        assert demand >= 0
        assert isinstance(demand, int)


class TestActiveGatheringSkillsCycleGuard:
    def test_recipe_cycle_does_not_loop(self):
        """active_gathering_skills walks recipe trees; a cyclic recipe must
        terminate via the visited guard (line 279) and still report the
        reachable gather skill."""
        gd = GameData()
        gd._crafting_recipes = {
            "alpha": {"beta": 1},
            "beta": {"alpha": 1, "raw_ore": 2},
        }
        gd._resource_drops = {"ore_rocks": "raw_ore"}
        gd._resource_skill = {"ore_rocks": ("mining", 1)}
        skills = gd.active_gathering_skills("alpha", None)
        assert "mining" in skills

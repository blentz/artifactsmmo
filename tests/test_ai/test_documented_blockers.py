"""Tests for the documented-blocker seeder."""

from artifactsmmo_cli.ai.blockers import (
    BlockerRegistry,
    seed_documented_blockers,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd_with_progression() -> GameData:
    gd = GameData()
    gd._monster_level = {
        "chicken": 1,         # already beatable at L2
        "yellow_slime": 3,    # near-future
        "skeleton": 18,       # too far
        "lich": 30,
    }
    gd._item_stats = {
        # Equippable items at various levels
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
        "iron_axe": ItemStats(code="iron_axe", level=10, type_="weapon",
                              crafting_skill="weaponcrafting", crafting_level=10),
        "steel_axe": ItemStats(code="steel_axe", level=20, type_="weapon",
                               crafting_skill="weaponcrafting", crafting_level=20),
        # Non-equippable (raw material)
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    gd._resource_skill = {
        "copper_rocks": ("mining", 1),
        "iron_rocks": ("mining", 5),
        "gold_rocks": ("mining", 15),
    }
    return gd


class TestSeedDocumentedBlockers:
    def test_seeds_all_distant_gates_by_default(self):
        """No cap by default — full progression map goes in the registry.
        Caller filters at use time."""
        reg = BlockerRegistry()
        state = make_state(level=2, skills={"weaponcrafting": 1, "mining": 1})
        seed_documented_blockers(reg, _gd_with_progression(), state)
        # skeleton (L18) and lich (L30) far beyond char L2 — included.
        assert "fight:skeleton" in reg.blockers
        assert "fight:lich" in reg.blockers
        # iron_axe / steel_axe craft gates are also distant but included.
        assert "craft:iron_axe" in reg.blockers
        assert "craft:steel_axe" in reg.blockers
        # Already-beatable monsters stay OUT (chicken at L1, char L2).
        assert "fight:chicken" not in reg.blockers

    def test_max_gap_filters_distant(self):
        """Callers wanting an actionable-only view can opt in to a cap."""
        reg = BlockerRegistry()
        state = make_state(level=2, skills={"weaponcrafting": 1, "mining": 1})
        seed_documented_blockers(reg, _gd_with_progression(), state, max_gap=5)
        assert "fight:skeleton" not in reg.blockers
        assert "craft:iron_axe" not in reg.blockers

    def test_adds_within_gap(self):
        reg = BlockerRegistry()
        # Char with mining=3 → iron_rocks (L5) is gap=2, within MAX.
        state = make_state(level=2, skills={"mining": 3, "weaponcrafting": 1})
        seed_documented_blockers(reg, _gd_with_progression(), state)
        assert "gather:iron_rocks" in reg.blockers
        b = reg.get("gather:iron_rocks")
        assert b is not None
        assert b.required_skill == "mining"
        assert b.required_skill_level == 5
        assert b.source == "documented"

    def test_adds_equip_gate_within_range(self):
        reg = BlockerRegistry()
        # Char L8 → iron_axe (item_level=10) gap=2, within MAX.
        state = make_state(level=8)
        seed_documented_blockers(reg, _gd_with_progression(), state)
        assert "equip:iron_axe" in reg.blockers

    def test_existing_blockers_take_precedence(self):
        """Discovered blockers (e.g. learned bank gate) override docs."""
        reg = BlockerRegistry()
        reg.mark_blocked("fight:yellow_slime", char_level=2,
                          unlock_monster="yellow_slime", required_level=3)
        # Same code → not overwritten by seed.
        state = make_state(level=2)
        seed_documented_blockers(reg, _gd_with_progression(), state)
        b = reg.get("fight:yellow_slime")
        assert b is not None
        assert b.source == "discovered"

    def test_returns_count(self):
        reg = BlockerRegistry()
        state = make_state(level=8, skills={"mining": 3, "weaponcrafting": 5})
        added = seed_documented_blockers(reg, _gd_with_progression(), state)
        assert added > 0

    def test_idempotent(self):
        reg = BlockerRegistry()
        state = make_state(level=8, skills={"mining": 3, "weaponcrafting": 5})
        seed_documented_blockers(reg, _gd_with_progression(), state)
        n1 = len(reg.blockers)
        seed_documented_blockers(reg, _gd_with_progression(), state)
        n2 = len(reg.blockers)
        assert n1 == n2

    def test_max_gap_param_caps_all_categories(self):
        """When max_gap is set, no seeded blocker exceeds it across any category."""
        reg = BlockerRegistry()
        state = make_state(level=2, skills={"weaponcrafting": 1})
        seed_documented_blockers(reg, _gd_with_progression(), state, max_gap=5)
        for _code, b in reg.blockers.items():
            if b.required_level > 0:
                assert b.required_level - state.level <= 5
            if b.required_skill_level > 0:
                cur = state.skills.get(b.required_skill, 0)
                assert b.required_skill_level - cur <= 5

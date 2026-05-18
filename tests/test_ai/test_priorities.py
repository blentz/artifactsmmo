"""Tests pinning the priority ladder ordering. If you change a constant in
priorities.py and one of these fails, that's the assertion you have to
think hardest about."""

from artifactsmmo_cli.ai import priorities


class TestLadderOrdering:
    def test_hp_critical_dominates_everything(self):
        for name in dir(priorities):
            if name.startswith("_"):
                continue
            value = getattr(priorities, name)
            if not isinstance(value, float):
                continue
            if name == "HP_CRITICAL":
                continue
            assert priorities.HP_CRITICAL > value, (
                f"HP_CRITICAL ({priorities.HP_CRITICAL}) must beat {name} ({value})"
            )

    def test_hard_prereqs_above_normal_pursuits(self):
        assert priorities.REACH_UNLOCK_LEVEL > priorities.FARM_ITEMS_BASE
        assert priorities.REACH_UNLOCK_LEVEL > priorities.FARM_MONSTER_BASE
        assert priorities.REACH_UNLOCK_LEVEL > priorities.UPGRADE_EQUIPMENT_BASE
        assert priorities.BANK_UNLOCK > priorities.FARM_MONSTER_BASE
        assert priorities.COMPLETE_TASK > priorities.FARM_MONSTER_BASE

    def test_strategic_above_tactical(self):
        assert priorities.LOW_YIELD_CANCEL > priorities.FARM_ITEMS_BASE
        assert priorities.LEVEL_SKILL > priorities.FARM_ITEMS_BASE
        assert priorities.LEVEL_SKILL > priorities.UPGRADE_EQUIPMENT_BASE

    def test_gather_materials_above_farm_items(self):
        """An in-flight material chain interrupts task work — otherwise
        the loop would never finish gathering for an upgrade."""
        assert priorities.GATHER_MATERIALS > priorities.FARM_ITEMS_BASE

    def test_grind_xp_caps_below_level_skill(self):
        """Skill-driven progression should beat generic XP grind."""
        assert priorities.GRIND_CHARACTER_XP_CEILING < priorities.LEVEL_SKILL

    def test_farm_items_above_farm_monster(self):
        """When an items task is active, it dominates monster grinding cold-start."""
        assert priorities.FARM_ITEMS_BASE > priorities.FARM_MONSTER_BASE

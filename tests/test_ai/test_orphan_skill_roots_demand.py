"""The gathering-skill demand gate on `_orphan_skill_roots`.

`_orphan_skill_roots` offers a "grind this skill" root for every skill no
gear item can name, which admits every gathering skill whether or not
anything wants it — two live characters ground fishing ~617 cycles each for 0
character XP while neither needed a fish. This is the THIRD CONJUNCT: a
gathering skill (`gather_demand.gathering_skills`) is admitted only when
`gather_demand` names it as UNMET demand from the roots already on offer.
"""

from artifactsmmo_cli.ai.actions import level_skill
from artifactsmmo_cli.ai.decisions.root import _gear_nameable_skills, _orphan_skill_roots
from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.gather_demand import gather_demand
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_gather_demand import _gd

_BOOTS = ObtainItem(code="iron_boots", quantity=1)


def _skills(state, gd, offered):
    return [g.skill for g in _orphan_skill_roots(state, gd, offered, NO_PROFILE_CONTEXT)]


def _orphan_demand(state, gd, offered):
    return gather_demand(offered, state, gd, NO_PROFILE_CONTEXT)


class TestGatheringSkillNeedsDemand:
    def test_dropped_when_nothing_demands_it(self):
        """R2D2's shape: mining is past every gate anything asks for.

        CONTROLLER RULING 3: the brief's own vacuity guard here
        (`assert "mining" in _skills(state, gd, [])`) asserts the gate is
        OFF — with the third conjunct in place, an empty `offered` is always
        empty demand, so that line can never hold once this task is done. The
        two conjuncts it stood in for are asserted directly instead, so this
        test still fails if either conjunct 1 or conjunct 2 is what actually
        removed mining, and not just the new one.
        """
        gd = _gd()
        state = make_state(level=20, skills={"mining": 10, "cooking": 1})
        # Vacuity guard, conjunct 1: no gear target can name mining in this
        # catalogue.
        assert "mining" not in _gear_nameable_skills(gd)
        # Vacuity guard, conjunct 2: mining has a genuinely open, XP-positive
        # rung at 10->11 — `iron_rocks` gathers at mining@10, right at the
        # character's current level.
        assert level_skill.LevelSkill(
            skill="mining", target_level=11).is_applicable(state, gd) is True
        # THE THIRD CONJUNCT: nothing demands mining, so `gather_demand` is
        # silent for it even with a root on offer (`iron_boots` needs
        # gearcrafting, not mining, at this character's level).
        assert _orphan_demand(state, gd, [_BOOTS]) == {}
        assert "mining" not in _skills(state, gd, [_BOOTS])

    def _gd_with_open_mining_floor(self):
        """`_gd()` plus a mining@1 gatherable, so `mining` at skill 1 has a
        genuinely open rung (conjunct 2) — `_gd()`'s only mining content,
        `iron_rocks`, gates at mining@10 and would leave conjunct 2 false at
        skill 1, which would make the tests below pass even with the third
        conjunct removed (the exact vacuity Ruling 3 warns against). The
        `_BOOTS` closure still bottoms out in `iron_ore`/mining@10 — untouched
        — so the DEMANDED level these tests check stays 10, not 1."""
        gd = _gd()
        gd._item_stats["copper_ore"] = ItemStats(
            code="copper_ore", level=1, type_="resource")
        gd._resource_drops_full["copper_rocks"] = [("copper_ore", 100, 1, 1)]
        # `best_gather_resource_drop`'s last step is `resource_drop_item`,
        # which reads the PRIMARY drop map — `resource_drops_full` alone is
        # enough for `_obtainable`'s `gatherable_drop_items()` union (how
        # `iron_ore` clears its own obtainability check in `_gd()`), but not
        # for the gather ARM of `LevelSkill.is_applicable` to name a drop.
        gd._resource_drops["copper_rocks"] = "copper_ore"
        gd._resource_skill["copper_rocks"] = ("mining", 1)
        return gd

    def test_kept_when_a_root_demands_it(self):
        """HAL's shape: a root's closure bottoms out in a leaf out of reach."""
        gd = self._gd_with_open_mining_floor()
        state = make_state(level=20, skills={"mining": 1, "cooking": 1})
        assert level_skill.LevelSkill(
            skill="mining", target_level=2).is_applicable(state, gd) is True
        assert "mining" in _skills(state, gd, [_BOOTS])

    def test_an_admitted_skill_emits_the_demanded_level(self):
        """Not C+1. `mining->2` completes and re-emits; `mining->10` is the ask."""
        gd = self._gd_with_open_mining_floor()
        state = make_state(level=20, skills={"mining": 1, "cooking": 1})
        roots = _orphan_skill_roots(state, gd, [_BOOTS], NO_PROFILE_CONTEXT)
        mining = next(g for g in roots if g.skill == "mining")
        assert mining.level == 10

    def test_a_non_gathering_skill_is_never_gated(self):
        """Cooking gathers nothing, so it never enters the conjunct and is the
        anti-Wait floor. Admitted with an empty demand set."""
        gd = _gd()
        # `gd._item_stats` delegates to the SAME `self.items.stats` dict
        # `all_item_stats` reads (`game_data.py`'s `_item_stats`/`all_item_stats`
        # properties), so mutating it in place is visible to both without a
        # second assignment — `all_item_stats` has no setter to assign through.
        gd._item_stats["cooked_gudgeon"] = ItemStats(
            code="cooked_gudgeon", level=1, type_="consumable",
            crafting_skill="cooking", crafting_level=1)
        # `gudgeon` itself must be a real gatherable leaf (a fishing catch), or
        # `has_grind_target`'s recursive `_obtainable` walk refuses the recipe
        # and cooking's conjunct-2 rung is never open — the SAME vacuity this
        # module's other tests guard against, just on the material side.
        gd._resource_drops_full["fishing_spot"] = [("gudgeon", 100, 1, 1)]
        gd._resource_skill["fishing_spot"] = ("fishing", 1)
        gd._crafting_recipes["cooked_gudgeon"] = {"gudgeon": 1}
        state = make_state(level=20, skills={"mining": 10, "cooking": 1})
        assert level_skill.LevelSkill(
            skill="cooking", target_level=2).is_applicable(state, gd) is True
        assert _orphan_demand(state, gd, []) == {}
        assert "cooking" in _skills(state, gd, [])

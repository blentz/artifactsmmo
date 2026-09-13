"""The craft-demand gate on `_orphan_skill_roots`' FIRST conjunct.

Conjunct 1 drops every gear-nameable skill (gearcrafting, weaponcrafting,
jewelrycrafting) on the grounds that a gear root naming one drives it through
the ordinary prerequisite seam. That holds while some gear root is plannable and
fails silently when none is — the skill is then excluded on the strength of a
mechanism with nothing to say about it.

Live Robby 2026-09-13: weaponcrafting 11 against character level 30, a gap of
-19 (twice the runner-up), an OPEN rung whose next step was two chicken fights,
and all five gear roots at `nodes=0, plan_len=0`. Measured craft demand across
every root on offer: `{}`. He ground cooking — a 55-porkchop rung, 9 levels
behind — for two days at 0 character XP.

The conjunct now ASKS instead of assuming: a gear-nameable skill is admitted
only when no root on offer demands it. Note the polarity is the MIRROR of the
gathering conjunct: a gathering skill needs demand to be admitted, a
gear-nameable skill needs the ABSENCE of demand, because demand means something
else already owns the climb.
"""

from artifactsmmo_cli.ai.craft_demand import craft_demand
from artifactsmmo_cli.ai.decisions.root import _gear_nameable_skills, _orphan_skill_roots
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_gather_demand import _gd as _gather_gd


def _gd() -> GameData:
    """Built on `test_gather_demand._gd`, whose shape is already known to
    produce a live orphan list, plus two weaponcrafted swords.

    `iron_sword` is weaponcrafted at 11 and `steel_sword` at 25, both from
    `iron_bar` <- `iron_ore` <- `iron_rocks`@mining10 — so a character at
    weaponcrafting 11 with mining past the gate has an in-level rung for the
    first and an out-of-reach gate on the second. `cooked_shrimp` gives
    cooking an in-level rung off a fished `shrimp` — the real game shape, and
    cooking's live role as the group's floor."""
    gd = _gather_gd()
    gd._item_stats = dict(gd._item_stats)
    gd._item_stats.update({
        "iron_sword": ItemStats(code="iron_sword", level=11, type_="weapon",
                                crafting_skill="weaponcrafting", crafting_level=11),
        "steel_sword": ItemStats(code="steel_sword", level=25, type_="weapon",
                                 crafting_skill="weaponcrafting", crafting_level=25),
        "cooked_shrimp": ItemStats(code="cooked_shrimp", level=21, type_="consumable",
                                   crafting_skill="cooking", crafting_level=21),
        "shrimp": ItemStats(code="shrimp", level=1, type_="resource"),
    })
    gd._crafting_recipes = dict(gd._crafting_recipes)
    gd._crafting_recipes.update({
        "iron_sword": {"iron_bar": 2},
        "steel_sword": {"iron_bar": 8},
        "cooked_shrimp": {"shrimp": 1},
    })
    gd._resource_drops_full = dict(gd._resource_drops_full)
    gd._resource_drops_full["shrimp_spot"] = [("shrimp", 100, 1, 1)]
    gd._resource_skill = dict(gd._resource_skill)
    gd._resource_skill["shrimp_spot"] = ("fishing", 1)
    return gd


def _state():
    """Robby's shape, minimised: weaponcrafting far behind the character with an
    in-level rung, cooking nearer with one too, mining past its gate."""
    return make_state(level=30,
                      skills={"weaponcrafting": 11, "cooking": 21,
                              "mining": 25, "fishing": 25})


def _skills(state, gd, offered):
    return [g.skill for g in _orphan_skill_roots(state, gd, offered, NO_PROFILE_CONTEXT)]


class TestGearNameableSkillAdmittedWhenUndemanded:
    def test_weaponcrafting_is_gear_nameable(self):
        """Vacuity guard. If weaponcrafting stopped being gear-nameable the
        tests below would pass for the wrong reason — they would be measuring a
        skill conjunct 1 never excluded in the first place."""
        assert "weaponcrafting" in _gear_nameable_skills(_gd())

    def test_admitted_when_no_root_demands_it(self):
        """Robby's shape: nothing on offer names a craft skill, so the seam that
        owes weaponcrafting its climb has nothing to say and the orphan group
        must offer one."""
        gd = _gd()
        state = _state()
        offered = [ReachCharLevel(level=40)]
        assert craft_demand(offered, state, gd, NO_PROFILE_CONTEXT) == {}
        assert "weaponcrafting" in _skills(state, gd, offered)

    def test_it_sorts_ahead_of_the_cooking_floor(self):
        """ORDER is unchanged — one integer, `skill level - character level`,
        furthest behind first. weaponcrafting at -19 simply beats cooking at -9
        once it is in the list at all. This is the assertion that was false
        while the skill was excluded before the sort ever ran."""
        gd = _gd()
        state = _state()
        order = _skills(state, gd, [ReachCharLevel(level=40)])
        assert order.index("weaponcrafting") < order.index("cooking")

    def test_dropped_when_a_root_does_demand_it(self):
        """The behaviour conjunct 1 exists for, preserved. A gear root asking
        for weaponcrafting 25 drives the climb through the prerequisite seam, so
        a rival standalone root would be the churn the conjunct prevents."""
        gd = _gd()
        state = _state()
        offered = [ObtainItem(code="steel_sword", quantity=1)]
        assert craft_demand(offered, state, gd, NO_PROFILE_CONTEXT) == {"weaponcrafting": 25}
        assert "weaponcrafting" not in _skills(state, gd, offered)

    def test_a_met_demand_does_not_suppress_it(self):
        """Demand is UNMET demand. A gear root naming weaponcrafting at a level
        already reached is not driving any climb, so it must not suppress one."""
        gd = _gd()
        state = make_state(level=30,
                           skills={"weaponcrafting": 25, "cooking": 21,
                                   "mining": 25, "fishing": 25})
        offered = [ObtainItem(code="steel_sword", quantity=1)]
        assert craft_demand(offered, state, gd, NO_PROFILE_CONTEXT) == {}
        assert "weaponcrafting" in _skills(state, gd, offered)

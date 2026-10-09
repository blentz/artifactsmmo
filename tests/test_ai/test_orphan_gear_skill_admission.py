"""`_orphan_skill_roots` admits a skill ONLY WHEN THE DAG DEMANDS IT.

USER 2026-10-08, "Only when demanded": "a skill climbs only when the
goal-action DAG demands it (gear, the consumable floor's tier food, a task).
Cooking rises when a better tier food is due, not before."

This replaced a rule that admitted a gear-nameable skill when nothing demanded
it (live Robby 2026-09-13, weaponcrafting 19 behind) and cooking
unconditionally. Live 2026-10-08 the unconditional cooking climb pulled fishing
in through its grind target: four characters ~100 cycles each on
`Gather(trout_spot)` with nothing asking for a fish.
"""

from dataclasses import replace

from artifactsmmo_cli.ai.craft_demand import craft_demand
from artifactsmmo_cli.ai.decisions.root import _orphan_skill_roots
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_gather_demand import _gd as _gather_gd


def _gd() -> GameData:
    """Built on `test_gather_demand._gd`, whose shape is already known to
    produce a live orphan list, plus two weaponcrafted swords.

    `iron_sword` is weaponcrafted at 11 and `steel_sword` at 25, both from
    `iron_bar` <- `iron_ore` <- `iron_rocks`@mining10 — so a character at
    weaponcrafting 11 with mining past the gate has an in-level rung for the
    first and an out-of-reach gate on the second. `cooked_shrimp` gives
    cooking an in-level rung off a fished `shrimp` — the real game shape."""
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
    gd.recipes_catalog.locations["shrimp_spot"] = [(2, 0)]
    gd.world.workshop_locations.update({"weaponcrafting": (0, 2), "cooking": (0, 3)})
    return gd


def _gd_with_trout() -> GameData:
    """`_gd` plus `cooked_trout`, a cooking-25 food off the same shrimp."""
    gd = _gd()
    gd._item_stats["cooked_trout"] = ItemStats(code="cooked_trout", level=25, type_="consumable",
                                               crafting_skill="cooking", crafting_level=25)
    gd._crafting_recipes["cooked_trout"] = {"shrimp": 2}
    return gd


def _state():
    """Robby's shape, minimised: weaponcrafting far behind the character with an
    in-level rung, cooking nearer with one too, mining past its gate."""
    return make_state(level=30,
                      skills={"weaponcrafting": 11, "cooking": 21,
                              "mining": 25, "fishing": 25})


def _skills(state, gd, offered, ctx=NO_PROFILE_CONTEXT):
    return [g.skill for g in _orphan_skill_roots(state, gd, offered, ctx)]


class TestOnlyWhenDemanded:
    def test_an_undemanded_skill_gets_no_climb(self):
        """Robby's shape: weaponcrafting 19 behind with an open rung, cooking
        with one too, and nothing on offer naming either. No climb."""
        gd = _gd()
        state = _state()
        offered = [ReachCharLevel(level=40)]
        assert craft_demand(offered, state, gd, NO_PROFILE_CONTEXT) == {}
        assert _skills(state, gd, offered) == []

    def test_a_demanded_skill_climbs_to_the_level_asked_for(self):
        gd = _gd()
        state = _state()
        offered = [ObtainItem(code="steel_sword", quantity=1)]
        assert craft_demand(offered, state, gd, NO_PROFILE_CONTEXT) == {"weaponcrafting": 25}
        assert _orphan_skill_roots(state, gd, offered, NO_PROFILE_CONTEXT) == (
            ReachSkillLevel(skill="weaponcrafting", level=25),)

    def test_a_met_demand_is_no_demand(self):
        gd = _gd()
        state = make_state(level=30,
                           skills={"weaponcrafting": 25, "cooking": 21,
                                   "mining": 25, "fishing": 25})
        offered = [ObtainItem(code="steel_sword", quantity=1)]
        assert craft_demand(offered, state, gd, NO_PROFILE_CONTEXT) == {}
        assert _skills(state, gd, offered) == []

    def test_a_skill_a_root_already_climbs_is_left_to_it(self):
        gd = _gd()
        state = _state()
        offered = [ObtainItem(code="steel_sword", quantity=1),
                   ReachSkillLevel(skill="weaponcrafting", level=12)]
        assert _skills(state, gd, offered) == []

    def test_the_consumable_floor_demands_its_tier_food(self):
        """Cooking rises when a better tier food is due: the fleet shortfall
        of `cooked_trout` (cooking 25) is DAG demand. The climb's rung is the
        in-level `cooked_shrimp` (cooking 21)."""
        gd = _gd_with_trout()
        state = _state()
        assert _skills(state, gd, []) == []
        ctx = replace(NO_PROFILE_CONTEXT, supply_shortfall=(("cooked_trout", 10),))
        assert _orphan_skill_roots(state, gd, [], ctx) == (
            ReachSkillLevel(skill="cooking", level=25),)

    def test_furthest_behind_first(self):
        """ORDER: one integer, `skill level - character level`. weaponcrafting
        at -19 ahead of cooking at -9."""
        gd = _gd_with_trout()
        state = _state()
        ctx = replace(NO_PROFILE_CONTEXT, supply_shortfall=(("cooked_trout", 10),))
        offered = [ObtainItem(code="steel_sword", quantity=1)]
        assert _skills(state, gd, offered, ctx) == ["weaponcrafting", "cooking"]

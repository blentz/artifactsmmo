"""Craft-demand projection: which CRAFTING skills the offered roots need.

The mirror of `gather_demand`, and it answers the question conjunct 1 of
`_orphan_skill_roots` was assuming rather than asking. That conjunct drops every
gear-nameable skill — gearcrafting, weaponcrafting, jewelrycrafting — on the
grounds that the gear seam names them when a gear root needs one. True whenever
some gear root is PLANNABLE; false otherwise, and live Robby 2026-09-13 was the
otherwise: weaponcrafting 11 against character level 30 (a gap of -19, the widest
on him by a factor of two) with all five of his gear roots resolving to
`nodes=0, plan_len=0`. Measured on his live state, the craft demand of every
root on offer was `{}` — nothing asked for weaponcrafting, and the conjunct that
would have offered it a rung had excluded it on the assumption something would.
"""

from artifactsmmo_cli.ai.craft_demand import craft_demand
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    """`steel_sword` <- `steel_bar`, the sword weaponcrafted at 25 and the bar
    smelted at mining 20 — one root whose closure names TWO craft skills at
    different depths, so a test can tell which one the walk reports."""
    gd = GameData()
    gd._item_stats = {
        "steel_sword": ItemStats(code="steel_sword", level=25, type_="weapon",
                                 crafting_skill="weaponcrafting", crafting_level=25),
        "steel_bar": ItemStats(code="steel_bar", level=20, type_="resource",
                               crafting_skill="mining", crafting_level=20),
        "iron_ore": ItemStats(code="iron_ore", level=1, type_="resource"),
        "feather": ItemStats(code="feather", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"steel_sword": {"steel_bar": 6, "feather": 2},
                            "steel_bar": {"iron_ore": 10}}
    return gd


class TestCraftDemand:
    def test_names_the_craft_skill_a_root_requires(self):
        state = make_state(level=25, skills={"weaponcrafting": 11, "mining": 25})
        assert craft_demand([ObtainItem(code="steel_sword", quantity=1)],
                            state, _gd(), NO_PROFILE_CONTEXT) == {"weaponcrafting": 25}

    def test_names_every_craft_skill_in_the_closure(self):
        """The intermediate bar's own craft gate counts too — a root can be
        blocked on a skill that never appears on the item it names."""
        state = make_state(level=25, skills={"weaponcrafting": 11, "mining": 1})
        assert craft_demand([ObtainItem(code="steel_sword", quantity=1)],
                            state, _gd(), NO_PROFILE_CONTEXT) == {
            "weaponcrafting": 25, "mining": 20}

    def test_silent_when_the_gate_is_already_met(self):
        """An UNMET demand only. A skill already at level asks for nothing, so
        `.get(skill)` is falsy exactly when nothing is waiting on it."""
        state = make_state(level=30, skills={"weaponcrafting": 25, "mining": 25})
        assert craft_demand([ObtainItem(code="steel_sword", quantity=1)],
                            state, _gd(), NO_PROFILE_CONTEXT) == {}

    def test_takes_the_highest_level_across_roots(self):
        gd = _gd()
        gd._item_stats["iron_dagger"] = ItemStats(
            code="iron_dagger", level=10, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=10)
        gd._crafting_recipes["iron_dagger"] = {"feather": 2}
        state = make_state(level=25, skills={"weaponcrafting": 1, "mining": 25})
        assert craft_demand([ObtainItem(code="iron_dagger", quantity=1),
                             ObtainItem(code="steel_sword", quantity=1)],
                            state, gd, NO_PROFILE_CONTEXT) == {"weaponcrafting": 25}

    def test_a_root_naming_no_item_asks_for_nothing(self):
        """`ReachCharLevel` names no item, so it cannot demand a craft skill.
        Deliberately NOT seeded through a grind target the way `gather_demand`
        seeds a `ReachSkillLevel`: this projection is asked ONLY of the roots
        already on offer, and seeding a skill root with its own grind target
        would let a candidate manufacture the demand that SUPPRESSES it."""
        state = make_state(level=25, skills={"weaponcrafting": 11})
        assert craft_demand([ReachCharLevel(level=40)],
                            state, _gd(), NO_PROFILE_CONTEXT) == {}

    def test_no_roots_is_no_demand(self):
        state = make_state(level=25, skills={"weaponcrafting": 11})
        assert craft_demand([], state, _gd(), NO_PROFILE_CONTEXT) == {}

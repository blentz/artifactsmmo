"""Gather-demand projection: which gathering skills the offered roots need."""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gather_demand import gather_demand
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachSkillLevel
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    """A catalogue with one craft whose material is a gathered leaf.

    `iron_boots` <- `iron_bar` <- `iron_ore`, and `iron_ore` is gathered from
    `iron_rocks` at mining@10 — the live shape, minimised.

    `iron_nails` is a SECOND mining craft, in-level at mining@1 (unlike
    `iron_bar`, which is craft_level=10 and so out of level for a mining@1
    character). Its purpose is entirely for `_seed`'s recursion guard: without
    it, `skill_grind_target("mining", state{mining: 1}, gd)` has no in-level
    mining recipe to select at all and returns `None` regardless of whether the
    guard runs, which is exactly what let the guard's own test pass with the
    guard deleted (a reviewer's probe). With `iron_nails` in the catalogue,
    removing the guard lets a mining `ReachSkillLevel` root seed itself with
    `iron_nails`, whose closure bottoms out at `iron_ore`/mining@10 — real,
    nonempty demand — so the guard's test now fails without the guard."""
    gd = GameData()
    gd._item_stats = {
        "iron_boots": ItemStats(code="iron_boots", level=10, type_="boots",
                                crafting_skill="gearcrafting", crafting_level=10),
        "iron_bar": ItemStats(code="iron_bar", level=10, type_="resource",
                              crafting_skill="mining", crafting_level=10),
        "iron_ore": ItemStats(code="iron_ore", level=10, type_="resource"),
        "iron_nails": ItemStats(code="iron_nails", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
    }
    gd._crafting_recipes = {"iron_boots": {"iron_bar": 6},
                            "iron_bar": {"iron_ore": 10},
                            "iron_nails": {"iron_ore": 1}}
    gd._resource_drops_full = {"iron_rocks": [("iron_ore", 100, 1, 1)]}
    gd._resource_skill = {"iron_rocks": ("mining", 10)}
    return gd


class TestGatherDemand:
    def test_names_the_skill_a_closure_leaf_gates_on(self):
        gd = _gd()
        state = make_state(level=20, skills={"mining": 1})
        assert gather_demand([ObtainItem(code="iron_boots", quantity=1)],
                             state, gd, NO_PROFILE_CONTEXT) == {"mining": 10}

    def test_silent_when_the_gate_is_already_met(self):
        gd = _gd()
        state = make_state(level=20, skills={"mining": 10})
        assert gather_demand([ObtainItem(code="iron_boots", quantity=1)],
                             state, gd, NO_PROFILE_CONTEXT) == {}

    def test_takes_the_highest_level_across_roots(self):
        """Two roots demanding the same skill collapse to the deeper gate."""
        gd = _gd()
        gd._resource_drops_full["coal_rocks"] = [("coal", 100, 1, 1)]
        gd._resource_skill["coal_rocks"] = ("mining", 20)
        gd._item_stats["coal"] = ItemStats(code="coal", level=20, type_="resource")
        gd._crafting_recipes["steel_boots"] = {"coal": 4, "iron_ore": 2}
        gd._item_stats["steel_boots"] = ItemStats(
            code="steel_boots", level=20, type_="boots",
            crafting_skill="gearcrafting", crafting_level=20)
        state = make_state(level=20, skills={"mining": 1})
        roots = [ObtainItem(code="iron_boots", quantity=1),
                 ObtainItem(code="steel_boots", quantity=1)]
        assert gather_demand(roots, state, gd, NO_PROFILE_CONTEXT) == {"mining": 20}

    def test_seeds_a_skill_root_through_its_grind_target(self):
        """A ReachSkillLevel root names no item, so its demand is invisible to a
        closure walk over `.code`. It is seeded with the item the character
        would craft for that rung.

        `iron_boots` itself needs gearcrafting@10 (`build_selectable_grind_
        candidates` filters to IN-LEVEL recipes only), so at gearcrafting@1
        `skill_grind_target` cannot select it — the fixture is enriched with
        `iron_gloves`, a level-1 gearcrafting recipe over the SAME iron_bar ->
        iron_ore chain, so the rung the character would actually grind next
        still bottoms out at mining@10."""
        gd = _gd()
        gd._item_stats["iron_gloves"] = ItemStats(
            code="iron_gloves", level=1, type_="gloves",
            crafting_skill="gearcrafting", crafting_level=1)
        gd._crafting_recipes["iron_gloves"] = {"iron_bar": 1}
        state = make_state(level=20, skills={"mining": 1, "gearcrafting": 1})
        demand = gather_demand([ReachSkillLevel(skill="gearcrafting", level=10)],
                               state, gd, NO_PROFILE_CONTEXT)
        assert demand == {"mining": 10}

    def test_a_gathering_skill_root_does_not_seed_itself(self):
        """Recursion guard: seeding a mining root from a mining grind target
        would let the root manufacture its own demand."""
        gd = _gd()
        state = make_state(level=20, skills={"mining": 1})
        assert gather_demand([ReachSkillLevel(skill="mining", level=2)],
                             state, gd, NO_PROFILE_CONTEXT) == {}

    def test_no_roots_is_no_demand(self):
        assert gather_demand([], make_state(), _gd(), NO_PROFILE_CONTEXT) == {}

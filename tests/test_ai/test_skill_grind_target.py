"""Tests for skill_grind_target: the shallow in-skill item to craft now."""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.skill_grind_target import (
    CACHE_MAX_ENTRIES,
    _cache_for,
    build_grind_candidates,
    skill_grind_target,
)
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
        "iron_dagger": ItemStats(code="iron_dagger", level=10, type_="weapon",
                                 crafting_skill="weaponcrafting", crafting_level=10),
        "wooden_staff": ItemStats(code="wooden_staff", level=3, type_="weapon",
                                  crafting_skill="weaponcrafting", crafting_level=3),
    }
    gd._crafting_recipes = {
        "copper_dagger": {"copper_bar": 6},
        "iron_dagger": {"iron_bar": 6},
        "wooden_staff": {"ash_plank": 4},
    }
    # The recipe leaves are gatherable resource drops, so every item is
    # obtainable (the obtainability filter only excludes un-gettable chains).
    gd._resource_drops = {"copper_rocks": "copper_bar", "iron_rocks": "iron_bar",
                          "ash_tree": "ash_plank"}
    # `acquire_steps` is now route-aware (`acquisition_cost.acquisition_actions`),
    # and a route is only servable where the executor could actually go: a CRAFT
    # needs a known workshop, a GATHER needs a live tile. Without these the stub
    # names no routes at all and every rung prices as unobtainable — which is the
    # model being honest about a world with nowhere to craft, not a bug.
    gd.world.workshop_locations = {"weaponcrafting": (0, 0)}
    gd.recipes_catalog.locations = {"copper_rocks": [(1, 0)], "iron_rocks": [(2, 0)],
                                    "ash_tree": [(3, 0)]}
    return gd


def test_picks_highest_craftable_at_current_level():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 3})
    assert skill_grind_target("weaponcrafting", state, gd) == "wooden_staff"


def test_prefers_materials_in_hand_over_higher_level():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 3},
                       inventory={"copper_bar": 6})
    assert skill_grind_target("weaponcrafting", state, gd) == "copper_dagger"


def test_the_BAG_is_free_but_the_BANK_is_a_priced_withdraw():
    """THE SEMANTIC CHANGE, stated as the thing that actually differs.

    Bank stock used to be added straight into `owned`, so a banked material cost
    NOTHING and this test asserted `copper_dagger` won outright on that basis.
    Under the route model only the BAG is free; the bank is a WITHDRAW route —
    one hop plus one action per unit — which here costs exactly what gathering
    the same bars costs, so a banked rung ties an unstocked one rather than
    beating it.

    That is why `wooden_staff` (4 `ash_plank`) now wins where `copper_dagger`
    (6 bars) used to: six withdraws are dearer than four gathers. The old model
    could not express the difference because it charged zero for both."""
    gd = _gd()
    def steps(state):
        return next(c.acquire_steps
                    for c in build_grind_candidates("weaponcrafting", state, gd)
                    if c.code == "copper_dagger")
    empty = steps(make_state(skills={"weaponcrafting": 3}))
    banked = steps(make_state(skills={"weaponcrafting": 3},
                              bank_items={"copper_bar": 6}))
    in_bag = steps(make_state(skills={"weaponcrafting": 3},
                              inventory={"copper_bar": 6}))
    assert in_bag < banked, "the bag must be free where the bank is not"
    assert banked == empty, (
        "here a withdraw and a gather are both one action per unit, so stocking "
        "the bank buys nothing over gathering — the model saying so is correct")


def test_none_when_nothing_craftable_at_level():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 0})
    assert skill_grind_target("weaponcrafting", state, gd) is None


def test_none_for_skill_with_no_recipes():
    gd = _gd()
    state = make_state(skills={"alchemy": 5})
    assert skill_grind_target("alchemy", state, gd) is None


def test_in_skill_item_without_recipe_is_skipped():
    # copper_axe matches the skill and level but has no crafting recipe entry,
    # so it is skipped; the highest item with a recipe wins instead.
    gd = _gd()
    gd._item_stats["copper_axe"] = ItemStats(
        code="copper_axe", level=3, type_="weapon",
        crafting_skill="weaponcrafting", crafting_level=3)
    state = make_state(skills={"weaponcrafting": 3})
    assert skill_grind_target("weaponcrafting", state, gd) == "wooden_staff"


def test_reserved_materials_exclude_recipe():
    """Trace 2026-06-11 19:22: the grind picked copper_helmet (6 copper_bar)
    while the committed copper_legs_armor held exactly 5 bars — the grind
    must not consume the committed objective's recipe inputs."""
    gd = _gd()
    # copper_dagger eats copper_bar; with copper_bar reserved, wooden_staff
    # (ash_plank) must win even though dagger has fewer mats missing.
    state = make_state(skills={"weaponcrafting": 3},
                       inventory={"copper_bar": 6})
    assert skill_grind_target("weaponcrafting", state, gd) == "copper_dagger"
    assert skill_grind_target(
        "weaponcrafting", state, gd, reserved=frozenset({"copper_bar"}),
    ) == "wooden_staff"


def test_reserved_can_exhaust_all_recipes():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 10})
    assert skill_grind_target(
        "weaponcrafting", state, gd,
        reserved=frozenset({"copper_bar", "iron_bar", "ash_plank"}),
    ) is None


def _gd_obtainability() -> GameData:
    """copper_dagger is obtainable (copper_bar <- copper_ore, a gatherable
    resource drop); wooden_staff is NOT (needs wooden_stick, which has no recipe
    and no resource drop / dropper) — the live weaponcrafting bug."""
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
        "wooden_staff": ItemStats(code="wooden_staff", level=1, type_="weapon",
                                  crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {
        "copper_dagger": {"copper_bar": 6},
        "copper_bar": {"copper_ore": 10},
        "wooden_staff": {"wooden_stick": 1, "ash_wood": 4},
    }
    # copper_ore + ash_wood are gatherable resource drops; wooden_stick is NOT.
    gd._resource_drops = {"copper_rocks": "copper_ore", "ash_tree": "ash_wood"}
    return gd


def test_skips_unobtainable_inskill_item_for_obtainable_one():
    """weaponcrafting grind must pick the OBTAINABLE copper_dagger, NOT
    wooden_staff (needs un-gettable wooden_stick) — even though wooden_staff has
    ash_wood on hand (fewer missing mats) and would win the old tie-break."""
    gd = _gd_obtainability()
    # ash_wood on hand makes wooden_staff "fewer missing" under the old ranking.
    state = make_state(skills={"weaponcrafting": 1, "mining": 1},
                       inventory={"ash_wood": 4, "wooden_stick": 0})
    assert skill_grind_target("weaponcrafting", state, gd) == "copper_dagger"


def test_cyclic_recipe_is_not_obtainable():
    """A recipe cycle (a <- b, b <- a) bottoms out in no gatherable leaf, so the
    item is NOT obtainable and the grind returns None (exercises the _obtainable
    cycle guard)."""
    gd = GameData()
    gd._item_stats = {
        "cyc_a": ItemStats(code="cyc_a", level=1, type_="weapon",
                           crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"cyc_a": {"cyc_b": 1}, "cyc_b": {"cyc_a": 1}}
    state = make_state(skills={"weaponcrafting": 1})
    assert skill_grind_target("weaponcrafting", state, gd) is None


def test_craft_level_breaks_tie_when_materials_equal():
    """Two feasible items with EQUAL missing materials (both fully on hand) ->
    the higher craft_level wins (more XP). Exercises the craft_level tie-break."""
    gd = _gd()
    # copper_dagger (lvl1, copper_bar:6) and wooden_staff (lvl3, ash_plank:4)
    # both have 0 missing -> tie on mats -> wooden_staff (higher level) wins.
    state = make_state(skills={"weaponcrafting": 3},
                       inventory={"copper_bar": 6, "ash_plank": 4})
    assert skill_grind_target("weaponcrafting", state, gd) == "wooden_staff"


def test_the_memo_returns_a_hit_for_an_identical_state():
    """`skill_grind_target` runs inside `LevelSkillAction.is_applicable`, which
    the planner calls PER NODE, and it was unmemoised. Within one search almost
    every node shares the determinants, so the memo turns a rebuild into a
    lookup — measured on a live-sized holding: 95ms cold, 31us warm."""
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 3})
    first = build_grind_candidates("weaponcrafting", state, gd)
    assert build_grind_candidates("weaponcrafting", state, gd) is first


def test_the_memo_key_notices_a_changed_inventory():
    """THE HONESTY CHECK. A memo whose key is too coarse is worse than no memo:
    it returns a stale answer and nothing ever fails. Holdings change
    `acquire_steps`, so a changed inventory MUST miss."""
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 3})
    first = build_grind_candidates("weaponcrafting", state, gd)
    changed = make_state(skills={"weaponcrafting": 3}, inventory={"copper_bar": 6})
    assert build_grind_candidates("weaponcrafting", changed, gd) is not first


def test_the_memo_key_notices_a_changed_skill_level():
    """Skill level drives the zero-xp band, so it belongs in the key — a stale
    list here would grind a rung that pays nothing."""
    gd = _gd()
    first = build_grind_candidates(
        "weaponcrafting", make_state(skills={"weaponcrafting": 3}), gd)
    later = build_grind_candidates(
        "weaponcrafting", make_state(skills={"weaponcrafting": 9}), gd)
    assert later is not first


def test_each_game_data_gets_its_own_cache():
    """Scoped by `id(game_data)` with a weakref purge, exactly as
    `equipment/loadout_cache` does, so two fixtures never serve each other's
    answers."""
    state = make_state(skills={"weaponcrafting": 3})
    assert (build_grind_candidates("weaponcrafting", state, _gd())
            is not build_grind_candidates("weaponcrafting", state, _gd()))


def test_the_cache_is_bounded():
    """Inventory churns every action, so unbounded keys would accumulate for the
    life of the process. The oldest entry is evicted at the bound."""
    gd = _gd()
    cache = _cache_for(gd)
    for i in range(CACHE_MAX_ENTRIES):
        cache[("filler", i, (), (), (), ())] = []
    build_grind_candidates("weaponcrafting", make_state(skills={"weaponcrafting": 3}), gd)
    assert len(cache) <= CACHE_MAX_ENTRIES


def test_out_of_level_rungs_are_never_priced():
    """The in-level hoist, stated as the thing that would regress.

    `iron_dagger` is weaponcrafting 10. At weaponcrafting 3 the selection core
    discards it on `craft_level > current_level` before ranking it — the
    theorem is `test_skill_grind_selection.
    test_out_of_level_candidates_cannot_change_the_selection` — so building a
    `GrindCandidate` for it (a full `acquisition_actions` route walk plus a full
    recursive obtainability walk) is pure waste. Live R2D2 at weaponcrafting 9:
    69 in-skill craftables, 10 in level, so 59 of 69 were priced only to be
    thrown away, and this function was 47.0s of a 67.3s from-scratch
    `greater_wooden_staff` search (profile 2026-08-13). Drop the
    `crafting_level > current_level` guard and the first set below grows back.
    """
    gd = _gd()
    at_three = {c.code for c in build_grind_candidates(
        "weaponcrafting", make_state(skills={"weaponcrafting": 3}), gd)}
    assert at_three == {"copper_dagger", "wooden_staff"}, at_three
    # Reaching the gate brings the rung back: this is a level test, not a
    # permanent exclusion.
    at_ten = {c.code for c in build_grind_candidates(
        "weaponcrafting", make_state(skills={"weaponcrafting": 10}), gd)}
    assert at_ten == {"copper_dagger", "wooden_staff", "iron_dagger"}, at_ten


def test_the_in_level_hoist_leaves_the_chosen_rung_alone():
    """The hoist changes what is BUILT, never what is PICKED. With six
    `iron_bar` in the bag `iron_dagger` costs ONE craft — cheaper than either
    in-level rung and higher-level on the tie-break — so a filter that leaked it
    into the ranking would change this answer to `iron_dagger`."""
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 3}, inventory={"iron_bar": 6})
    assert skill_grind_target("weaponcrafting", state, gd) == "wooden_staff"

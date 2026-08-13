"""The deep-chain mispricing, against the REAL catalog.

Live R2D2 2026-08-06 (L12, weaponcrafting 5): 129 `LevelSkill(weaponcrafting->10)`
cycles across two runs moved weaponcrafting XP exactly ZERO times. Every cycle
returned `ok`. The skill sat at level 5 with 664 XP the whole time.

MECHANISM. The grind picked `sticky_sword` — a perfectly valid rung: same skill,
in level, obtainable, and xp-positive (craft level 5 at skill 5, so the craft
really would pay). The rung was never the problem. The RANKING was: the selector
ordered candidates by `mats_missing`, the count of recipe entries not currently
held, and

    sticky_sword      recipe {copper_bar: 5, yellow_slimeball: 2}   -> 5 missing
    apprentice_gloves recipe {feather: 6}                           -> 6 missing

so the sword won by one. But each `copper_bar` is 10 `copper_ore`, so the sword
is ~51 actions and the gloves LOOK like 7. Worse, at mining 12 the `copper_rocks`
gather that mints that ore is itself grey (gap 11), so each of those ~50 cycles
paid nothing in EITHER skill, and the chain never reached the craft that would
have paid weaponcrafting.

THE ARCHITECTURAL POINT. This was the THIRD recurrence of one flaw — a cost proxy
that cannot see past the first level of a recipe. The first two (`apprentice_gloves`
over `copper_dagger` 2026-06-24; grey `ash_plank` over `spruce_plank` 2026-08-05)
were each patched by adding ANOTHER key to the ordering — `wanted`, then the
`xp_positive` filter. Both were correct on their own terms and neither touched the
proxy that was lying. `acquire_steps` replaces it with the whole-closure action
count (`min_gathers + min_crafts`), reusing the SAME proved bound the planner's
reachability gate uses, so the codebase has one notion of "how much work is this"
instead of two that disagree.

THE FOURTH RECURRENCE, 2026-08-09. "The gloves are 7" was itself the same error
one level down. `apprentice_gloves` is `{feather: 6}`, and a feather is a 1-in-8
CHICKEN DROP — about 48 kills, not 6 gathers. `min_gathers` calls anything
without a recipe a raw gatherable, so the fix above swapped one lying proxy for
another, and the bot went and farmed chickens: live R2D2 2026-08-08 ran 198
chicken fights inside `LevelSkill(weaponcrafting->10)`, every one at xp 0, and
weaponcrafting stayed at level 6.

`acquire_steps` now comes from `acquisition_cost.acquisition_actions`, which
prices every route the executor can serve. Against this catalog:

    apprentice_gloves   OLD   7   NEW      75    {feather: 6}  -- 1-in-8 drop
    sticky_sword        OLD  51   NEW      61    {yellow_slimeball: 2, copper_bar: 5}
    copper_dagger       OLD  61   NEW      69    {copper_bar: 6}
    wooden_staff        OLD   6   NEW 1000007    needs the un-gettable wooden_stick

So the selection inverts AGAIN, to `sticky_sword` — and that is the honest
answer, not a return of the one-level proxy: the sword got DEARER too (51 -> 61),
it simply got dearer by less. Note the last row: the route-aware number also
prices the `wooden_staff` trap that the separate `obtainable` filter was added to
patch in 2026-06-13. One quantity now does the work of both proxies.

These tests assert the SELECTED RUNG and its real cost against the live catalog —
not that a helper returns a number — because the bug was a decision that looked
correct at every individual step.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions
from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.min_crafts import min_crafts
from artifactsmmo_cli.ai.min_gathers import min_gathers
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.skill_xp_positive import skill_xp_positive
from artifactsmmo_cli.ai.tiers.skill_grind_target import (
    build_selectable_grind_candidates,
    is_obtainable,
    skill_grind_target,
)
from artifactsmmo_cli.ai.world_state import WorldState

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

SCENARIO = "l12_deep_chain_grind"
SKILL = "weaponcrafting"


@pytest.fixture(scope="module")
def game_data() -> GameData:
    return load_bundle_game_data(BUNDLE)


@pytest.fixture
def state(game_data: GameData) -> WorldState:
    return scenario_state(SCENARIOS[SCENARIO], game_data)


def _steps(code: str, state: WorldState, game_data: GameData) -> int:
    bank = state.bank_items or {}
    owned = {c: state.inventory.get(c, 0) + bank.get(c, 0)
             for c in set(state.inventory) | set(bank)}
    recipes = game_data.crafting_recipes
    return (min_gathers(code, 1, recipes, owned)
            + min_crafts(code, 1, recipes, owned))


def _routed(code: str, state: WorldState, game_data: GameData) -> int:
    """The live measure: every route the executor can currently serve."""
    return acquisition_actions(code, 1, state, game_data, NO_PROFILE_CONTEXT,
                               equip=False)


def test_scenario_registered() -> None:
    assert SCENARIO in SCENARIOS


def test_the_premise_straight_from_the_catalog(game_data: GameData,
                                               state: WorldState) -> None:
    """The trap is a catalog fact. Both rungs are same-skill, in-level and
    xp-positive — the ONLY thing separating them is cost, and the old proxy got
    that backwards."""
    assert state.skills[SKILL] == 5
    for code in ("sticky_sword", "apprentice_gloves"):
        stats = game_data.item_stats(code)
        assert stats.crafting_skill == SKILL
        assert stats.crafting_level <= state.skills[SKILL]
        assert skill_xp_positive(stats.crafting_level, state.skills[SKILL]) is True

    bank = state.bank_items or {}
    owned = {c: state.inventory.get(c, 0) + bank.get(c, 0)
             for c in set(state.inventory) | set(bank)}
    # The OLD key: recipe entries not held. It ranks the sword CHEAPER.
    def mats_missing(code: str) -> int:
        return sum(max(0, qty - owned.get(mat, 0))
                   for mat, qty in game_data.crafting_recipe(code).items())
    assert mats_missing("sticky_sword") < mats_missing("apprentice_gloves")
    # The SECOND proxy inverts it, by a wide margin — and is also wrong, because
    # it prices the gloves' six feathers as six gathers.
    assert _steps("sticky_sword", state, game_data) > \
        3 * _steps("apprentice_gloves", state, game_data)
    # The ROUTE-AWARE cost inverts it back, because a feather is a 1-in-8 drop.
    assert game_data.monsters_dropping("feather") == [("chicken", 8, 1, 1)]
    assert _routed("apprentice_gloves", state, game_data) > \
        _routed("sticky_sword", state, game_data)


def test_grind_picks_the_chain_that_is_actually_cheap(game_data: GameData,
                                                     state: WorldState) -> None:
    """The rung must be the one that is actually cheap to BUILD.

    This asserted `apprentice_gloves` until 2026-08-09, on the strength of a
    measure that priced its six feathers as six gathers. They are a 1-in-8
    chicken drop — ~48 kills — and the bot duly farmed chickens for hours. The
    rung that is genuinely cheapest here is `sticky_sword`, and neither of the
    two earlier proxies could see it."""
    assert skill_grind_target(SKILL, state, game_data) == "sticky_sword"


def test_a_drop_fed_rung_is_dearer_than_its_recipe_lines_suggest(
        game_data: GameData, state: WorldState) -> None:
    """The defect isolated to one rung: `apprentice_gloves` lists ONE recipe line
    and prices at 7 under the old measure, but every unit of that line is a
    1-in-8 monster drop."""
    assert game_data.crafting_recipe("apprentice_gloves") == {"feather": 6}
    assert _steps("apprentice_gloves", state, game_data) < 10
    assert _routed("apprentice_gloves", state, game_data) > 50


def test_selected_rung_is_the_cheapest_feasible_one(game_data: GameData,
                                                    state: WorldState) -> None:
    """Stronger and proxy-independent: whatever is selected must minimise
    `acquire_steps` over every feasible candidate. This is the property the
    ordering theorems state, checked against the real catalog rather than
    hand-built candidates."""
    lvl = state.skills[SKILL]
    feasible = [c for c in build_selectable_grind_candidates(SKILL, state, game_data)
                if c.craft_skill == SKILL and c.craft_level <= lvl
                and c.obtainable and c.xp_positive]
    assert feasible, "scenario must offer at least one feasible rung"
    rung = skill_grind_target(SKILL, state, game_data)
    chosen = next(c for c in feasible if c.code == rung)
    assert chosen.acquire_steps == min(c.acquire_steps for c in feasible)


def test_hoisted_cost_counts_the_whole_chain(game_data: GameData,
                                             state: WorldState) -> None:
    """The hoist must cost the CLOSURE, not the first level, and it must cost it
    by ROUTE. `copper_bar` is not held, so sticky_sword's cost has to include the
    ore behind the bars — the term the first proxy omitted — and the gloves' cost
    has to include the chicken kills behind the feathers, which is the term the
    second proxy omitted."""
    cands = {c.code: c for c in build_selectable_grind_candidates(SKILL, state, game_data)}
    sword = cands["sticky_sword"]
    # 5 bars x 10 ore each, less the single ore held, plus the crafts and hops.
    assert sword.acquire_steps >= 45, sword.acquire_steps
    assert sword.acquire_steps == _routed("sticky_sword", state, game_data)
    # The hoist is the ROUTE-aware number, strictly above the recipe-closure one.
    assert sword.acquire_steps > _steps("sticky_sword", state, game_data)
    # And the drop-fed rung is no longer the bargain its recipe line implies.
    assert cands["apprentice_gloves"].acquire_steps > 50


# --- one test per TIER of material, because each tier is priced by a different
# --- route and each has had its own bug.

def test_tier_gathered_costs_one_action_per_unit(game_data: GameData,
                                                 state: WorldState) -> None:
    """GATHERED tier. A resource with a live tile costs one gather per unit plus
    one hop, and multi-yield nodes divide that. This is the only tier the very
    first proxy ever got right."""
    assert "copper_ore" in game_data.gatherable_drop_items()
    bare = replace(state, inventory={}, bank_items={})
    one = acquisition_actions("copper_ore", 1, bare, game_data,
                              NO_PROFILE_CONTEXT, equip=False)
    ten = acquisition_actions("copper_ore", 10, bare, game_data,
                              NO_PROFILE_CONTEXT, equip=False)
    assert 1 <= one <= 3, one          # one hop plus a gather
    assert ten > one, "quantity must cost more"
    # The hop is paid ONCE however many units, so ten units is not ten times one.
    assert ten < 10 * one


def test_tier_crafted_costs_its_whole_closure(game_data: GameData,
                                              state: WorldState) -> None:
    """CRAFTED tier. `copper_bar` is 10 `copper_ore` plus a craft, so it must
    cost an order more than the ore itself — the term `mats_missing` omitted and
    the 2026-08-06 fix restored."""
    bare = replace(state, inventory={}, bank_items={})
    assert game_data.crafting_recipe("copper_bar")
    assert _routed("copper_bar", bare, game_data) > \
        3 * _routed("copper_ore", bare, game_data)


def test_tier_dropped_costs_its_expected_kills(game_data: GameData,
                                               state: WorldState) -> None:
    """DROPPED tier. THE TIER THAT CAUSED THE LIVE BUG. A feather is a 1-in-8
    chicken drop, so one costs several fights — not the single gather
    `min_gathers` charges for anything lacking a recipe."""
    bare = replace(state, inventory={}, bank_items={})
    assert game_data.crafting_recipe("feather") is None
    assert game_data.monsters_dropping("feather") == [("chicken", 8, 1, 1)]
    routed = _routed("feather", bare, game_data)
    assert routed > 4, routed
    assert routed > min_gathers("feather", 1, game_data.crafting_recipes, {})


def test_tier_held_in_the_bag_is_free(game_data: GameData,
                                      state: WorldState) -> None:
    """HELD tier. What is already in the bag costs nothing, and is SPENT — the
    invariant that keeps this a bound on one coherent plan."""
    holding = replace(state, inventory={"copper_ore": 5}, bank_items={})
    assert _routed("copper_ore", holding, game_data) == 0


def test_tier_banked_is_a_priced_withdraw(game_data: GameData,
                                          state: WorldState) -> None:
    """BANKED tier. A banked copy is a WITHDRAW route, not free holdings — the
    change that stopped `J` crediting the same copy twice."""
    banked = replace(state, inventory={}, bank_items={"copper_ore": 5})
    cost = _routed("copper_ore", banked, game_data)
    assert cost > 0, "the bank is not the bag"
    assert cost <= _routed("copper_ore", replace(state, inventory={},
                                                 bank_items={}), game_data)


def test_tier_unobtainable_prices_out_rather_than_lying(game_data: GameData,
                                                        state: WorldState) -> None:
    """UNOBTAINABLE tier. `wooden_staff` needs `wooden_stick`, which nothing
    produces — the 2026-06-13 livelock that the separate `obtainable` filter was
    added to patch. The route-aware number prices it out directly, so one
    quantity now does the work of both proxies."""
    bare = replace(state, inventory={}, bank_items={})
    assert "wooden_stick" in (game_data.crafting_recipe("wooden_staff") or {})
    assert _routed("wooden_staff", bare, game_data) >= UNOBTAINABLE_PER_UNIT
    # ...where the old measure called it one of the cheapest rungs on the board.
    assert _steps("wooden_staff", bare, game_data) < 10


def test_a_SECONDARY_drop_is_recognised_as_gatherable(game_data: GameData,
                                                      state: WorldState) -> None:
    """THE PRIMARY-MAP BLINDNESS, pinned.

    `resource_drops` keeps only the rate-best drop per resource, so it sees 26 of
    the 43 gathered items. The 17 it misses are every SECONDARY drop: the five
    gem stones (1-in-100..200 off ordinary rocks), apple, algae, coconut, the
    saps, and `event_ticket`.

    `is_obtainable` tested membership against that primary map and then fell
    through to `drop_obtainable`, which asks about MONSTERS — so a rung needing a
    gem stone was judged unobtainable and filtered out, when it is an ordinary
    gather. Fixed by consulting the full union."""
    primary = set(game_data.resource_drops.values())
    full = game_data.gatherable_drop_items()
    hidden = sorted(full - primary)
    assert hidden, "fixture drift: no secondary-drop item to test with"
    for code in hidden:
        assert game_data.crafting_recipe(code) is None or True
        assert is_obtainable(code, state, game_data, frozenset()), (
            f"{code} is gatherable but read as unobtainable — the primary-only "
            "map is back")


def test_the_primary_map_really_is_narrower(game_data: GameData) -> None:
    """Guards the premise of the test above: if these two ever coincide, the
    case it protects has evaporated and it would pass vacuously."""
    primary = set(game_data.resource_drops.values())
    assert primary < game_data.gatherable_drop_items()

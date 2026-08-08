"""CHARACTERISATION OF A BUG — today's `acquire_cost`, pinned so the fix moves it.

Every number asserted here is WRONG and is expected to change. These tests exist
so the increments of the unified-acquisition epic
(`docs/PLAN_unified_acquisition_objective.md`) have a baseline that moves
visibly, instead of a silent re-ranking nobody can attribute.

**Do not read any assertion in this file as intended behaviour.** When an
increment lands, the corresponding assertion should be UPDATED, and the update
is the deliverable. A failure here means the fix is working.

THE DEFECT. `J`'s `acquire_cost` WAS `ai/min_plan_length` until the activation
commit; these tests call it directly, so they keep pinning the retired model as a
museum piece rather than as the live one. It models exactly three actions —
gather, craft, equip — and treats **any item without a recipe as a raw
gatherable costing one gather**. It has no notion of vendors, monsters,
currency, the bank, or skill gates. So a route it cannot express is not priced
expensively; it is priced at very nearly nothing, because the item looks raw.

The bias runs the opposite way from the obvious guess, which is why it survived:
nobody looks for a bug that makes the hard thing look cheap.
"""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.equipment.loadout_cache import pick_loadout_cached
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.gear_value_core import Rank
from artifactsmmo_cli.ai.learning.projections import cheapest_path_to_level
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.min_plan_length import min_plan_length
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.tiers.branch_objective import gear_candidate
from artifactsmmo_cli.ai.tiers.progression_tree_core import GearCandidate

_BUNDLE = (Path(__file__).resolve().parent / "scenarios" / "fixtures"
           / "gamedata_bundle.json")


@pytest.fixture(scope="module")
def game_data():  # type: ignore[no-untyped-def]
    return load_bundle_game_data(_BUNDLE)


def _cost(game_data, code: str) -> int:  # type: ignore[no-untyped-def]
    """`acquire_cost` exactly as `tiers/branch_objective.gear_candidate` computes
    it — same arguments, same `equip=True`, nothing held. Calling the production
    function rather than restating its formula, so this cannot drift into
    characterising a copy of the bug instead of the bug."""
    return min_plan_length(code, 1, game_data.crafting_recipes, {},
                           game_data.max_gather_yield, equip=True)


def test_a_recipeless_item_costs_one_gather_plus_one_equip(game_data) -> None:  # type: ignore[no-untyped-def]
    """The root of the whole defect, stated as a pure property.

    `min_gathers` calls anything absent from `recipes` a raw material, so the
    cost of an item is decided by whether it HAS A RECIPE — never by how it is
    actually obtained. This one line is why the four cases below all come out
    the same."""
    assert "not_a_real_item" not in game_data.crafting_recipes
    assert _cost(game_data, "not_a_real_item") == 2


def test_a_fifty_thousand_gold_purchase_costs_two_actions(game_data) -> None:
    """`backpack` is sold by `nomadic_merchant` for **50,000 gold** and has no
    recipe, is not gatherable, and drops from nothing. `J` prices acquiring it
    at 2 — the same as picking up two copper ore, and cheaper than any craft in
    the game.

    Increment 2 replaces this with `hop + 1 purchase + cost of 50,000 gold`."""
    assert game_data.npc_purchases("backpack") == [
        ("nomadic_merchant", 50000, "gold")]
    assert game_data.crafting_recipe("backpack") is None
    assert _cost(game_data, "backpack") == 2


def test_an_item_currency_purchase_is_equally_free(game_data) -> None:
    """`astralyte_crystal` costs 12 `tasks_coin` — a currency that must itself be
    earned by completing tasks. Neither the purchase nor the currency chain is
    priced. Increment 2 prices the currency RECURSIVELY, which is what makes
    this case different from the gold one rather than a duplicate of it."""
    assert game_data.npc_purchases("astralyte_crystal") == [
        ("tasks_trader", 12, "tasks_coin")]
    assert _cost(game_data, "astralyte_crystal") == 2


def test_an_open_ended_drop_farm_costs_two_actions(game_data) -> None:
    """`feather` and `wolf_hair` come only from killing monsters at a 1-in-N
    drop rate. `J` prices each at 2, modelling neither the kills nor the rests
    they force.

    The knowledge is not missing from the repo — `ai/monster_drop_selection`
    computes expected kills as an exact `Fraction` and is proved in
    `formal/Formal/MonsterDropSelection.lean`. It is simply not wired to
    pricing. Increment 2 wires it, reusing `fight_loop_cost.cycles_per_kill` so
    a drop-farm and a level-grind are quoted in identical whole-loop cycles."""
    for code in ("feather", "wolf_hair"):
        assert game_data.monsters_dropping(code), f"{code} should be drop-sourced"
        assert game_data.crafting_recipe(code) is None
        assert _cost(game_data, code) == 2


def test_craft_chains_are_the_one_route_priced_correctly(game_data) -> None:
    """The contrast that makes the defect legible. A craft chain is walked
    properly and costs what it costs — so `J` is not uniformly blind, it is
    blind on exactly the routes `min_plan_length` cannot express. A uniform
    error would cancel out of a ranking; this one does not."""
    assert _cost(game_data, "iron_sword") == 65
    assert _cost(game_data, "wisdom_amulet") == 50


def test_a_50000_gold_backpack_is_cheaper_than_two_copper_ore(game_data) -> None:
    """The comparison the ranking actually makes, in one assertion.

    `J` chooses between candidates by adding `acquire_cost` to projected cycles.
    On today's model, acquiring a 50,000-gold vendor item costs strictly LESS
    than acquiring two copper ore off the ground. Any ranking built on that is
    deciding on a fiction, however sound the objective above it.

    (One ore ties the backpack at 2 rather than losing — the fiction is bounded
    below by one gather, not by zero. Two is the smallest quantity that makes
    the ordering strict, and stating it that way keeps the assertion true rather
    than merely rhetorical.)"""
    two_ore = min_plan_length("copper_ore", 2, game_data.crafting_recipes, {},
                              game_data.max_gather_yield, equip=True)
    assert _cost(game_data, "backpack") < two_ore


def test_a_wisdom_ITEM_NOW_REACHES_THE_PROJECTION(game_data) -> None:
    """INCREMENT 3, and a CORRECTION to how it was first demonstrated.

    The original version of this test used `wisdom_amulet` and concluded that
    its wisdom 60 projected as zero because `ProjectedStats` had no `wisdom`
    field. The code claim was true — `cheapest_path_to_level` read
    `state.wisdom`, the total for gear already WORN — but the DEMONSTRATION was
    confounded: `wisdom_amulet` carries `conditions [('level', 14)]` and the
    scenario character is level 12, so `pick_loadout_cached` correctly refused to
    wear it. It would have projected zero whatever `ProjectedStats` contained.

    A measurement that cannot distinguish two explanations is not evidence for
    either. This version uses `adventurer_vest` — level 10, wisdom 20, actually
    wearable — so the only thing under test is whether the stat reaches the
    projection.

    Before increment 3 this was 0. It is now 20."""
    state = scenario_state(SCENARIOS["l12_deep_chain_grind"], game_data)
    vest = game_data.item_stats("adventurer_vest")
    assert vest.wisdom == 20
    assert vest.level <= state.level, "fixture drift: the vest must be wearable"

    holding = replace(state, inventory={**state.inventory, "adventurer_vest": 1},
                      hp=state.max_hp)
    projected = project_loadout_stats(
        holding, pick_loadout_cached(Rank(), holding, game_data), game_data)
    assert state.wisdom == 0
    assert projected.wisdom == 20


def test_wisdom_makes_a_COMPLETING_walk_cheaper(game_data) -> None:
    """The payoff, in the only band where `J` can see it.

    Below the top band every candidate is UNREACHABLE and S-006 ranks by
    furthest progress, then cost — the `J` sum never consults `cycles_to_fifty`
    there, so a wisdom item changes the ranking by nothing however well it is
    projected. That is a real limit of the projection (it models no acquisitions
    along the way), not of this increment, and it is why the level-12 scenario
    shows `reach=17` with and without the vest.

    Given a walk that COMPLETES, wisdom pays: 222.2 cycles -> 200.0.

    Asserts the DIRECTION only. A real item bundles stats — the vest also
    carries resistance and hp, which move `rest_cycles_per_fight` — so
    attributing the whole 10% to wisdom would be a claim this test cannot
    support."""
    state = scenario_state(SCENARIOS["l12_deep_chain_grind"], game_data)
    store = LearningStore(db_path=":memory:", character="wisdom_probe")
    store.start_session()
    try:
        near = replace(state, level=16, xp=0, max_xp=1000, inventory={})
        bare = cheapest_path_to_level(17, near, store, game_data)
        wise = cheapest_path_to_level(
            17, replace(near, inventory={"adventurer_vest": 1}), store, game_data)
    finally:
        store.end_session(exit_reason="normal")
        store.close()
    assert not bare.blocked and not wise.blocked
    assert wise.total_cycles < bare.total_cycles


def test_the_skill_gate_is_invisible_to_the_cost(game_data) -> None:
    """`iron_sword` needs weaponcrafting 10. Its cost is the SAME whether the
    character is at weaponcrafting 1 or 10, because `min_plan_length` takes no
    state beyond holdings.

    `obtain_sources._craft_sources` meanwhile EXCLUDES the craft route outright
    when the gate is unmet, so the two models disagree about the same item:
    one says it costs 65, the other says there is no way to craft it at all.
    Increment 1b makes both say 'it costs the grind plus the craft'."""
    stats = game_data.item_stats("iron_sword")
    assert stats.crafting_skill == "weaponcrafting"
    assert stats.crafting_level == 10
    # No skill argument exists to pass — that is the point.
    assert _cost(game_data, "iron_sword") == 65


def test_J_NOW_USES_THE_ROUTE_AWARE_COST(game_data) -> None:
    """ACTIVATION, asserted where it can be seen — `J`'s own `acquire_cost`.

    Green tests are not runtime activation (`feedback_verify_runtime_activation`),
    and this epic's own core sat INERT for four commits on purpose. This test
    exists so the switch cannot silently revert: it compares what
    `gear_candidate` actually reports against what `min_plan_length` would have
    said, and fails if they agree.

    Measured at the switch: `iron_sword` 65 -> 96 (venue hops plus the
    weaponcrafting gate), `copper_dagger` 62 -> 70, `feather` 2 -> 14.

    The characterisation tests ABOVE still pass because they call
    `min_plan_length` directly — they pin the old model as a museum piece, not
    as the live one. If both this and those ever agree, activation has been
    undone."""
    state = scenario_state(SCENARIOS["l12_deep_chain_grind"], game_data)
    store = LearningStore(db_path=":memory:", character="activation_probe")
    store.start_session()
    try:
        candidate = gear_candidate(
            GearCandidate(slot="weapon_slot", code="iron_sword",
                          gain=Fraction(1), level=10),
            state, store, game_data)
    finally:
        store.end_session(exit_reason="normal")
        store.close()
    assert candidate.acquire_cost != _cost(game_data, "iron_sword")
    assert candidate.acquire_cost > _cost(game_data, "iron_sword")

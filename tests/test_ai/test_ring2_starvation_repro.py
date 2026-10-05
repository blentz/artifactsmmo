"""Headline regression test for the ring2 arbiter-starvation bug.

The bug: an achievable craftable gear root (a 2nd `iron_ring` for
`ring2_slot`) starved forever behind a stuck, higher-value, drop-gated root
(`wolf_ears` helmet). The walk's slot order is a pure, history-free total
order, so a root that can never actually be COMPLETED (its only source is a
monster the character cannot beat) heads it on every cycle.

The first fix aged the focused root down a fall-off curve and interleaved the
slots with a d'Hondt scheduler. Phase 4-2b replaced both with facts about the
intention: an intention that makes no progress ends `stalled`, and one that
spends its cycle budget YIELDS its goal for one turn — the arbiter tries it
behind every peer (`intention_progress.demote_yielded`, tested in
`test_intention_budget.py`). This file pins the walk half of that answer: the
walk keeps the craftable ring on offer as the stuck root's first alternative,
which is what the yielded turn goes to."""

from dataclasses import replace
from pathlib import Path

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.scenario import (
    ScenarioCharacter,
    scenario_state,
)
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, is_attainable_now
from artifactsmmo_cli.ai.tiers.strategy import StrategyEngine
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai._monster_fixture import fill_monster_stat_defaults

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"

_UNBEATABLE_MONSTER = "ancient_wolf"
"""Level-40, hp 99999, attack fire 9999 dropper of `wolf_ears` — mirrors the
established `test_tiers_objective.py::_gd_drop_recipes` unbeatable-dragon
idiom (huge stats, no defeat possible). The scenario character carries the
harness's zero-attack default (no `derive_combat_stats`), so `is_winnable`
already reads False against EVERY monster including this one — the inflated
stats are kept anyway so the "cannot beat" premise holds even if a future
edit gives the character nonzero attack."""


def _stuck_wolf_ears_plus_craftable_ring2() -> tuple[WorldState, GameData, CharacterObjective]:
    """`iron_ring` (ring, level 1, craftable from the gatherable `iron_ore`)
    vs. `wolf_ears` (helmet, level 1, a PURE monster drop with no craft
    recipe, from `_UNBEATABLE_MONSTER`). The character already wears
    `iron_ring` in `ring1_slot` (so only `ring2_slot` carries any ring gain),
    `ring2_slot` is empty, and `helmet_slot` is empty (wolf_ears is a full
    upgrade from nothing).

    wolf_ears's hp_bonus (100 -> pursuit_value 100000) dwarfs iron_ring's
    (1 -> pursuit_value 1000), so wolf_ears is the argmax winner from cycle 0
    and stays the "highest-value" root at every cycle (the state never
    changes across the test's decide() loop, so the gain figures are stable).

    wolf_ears is held 1-off in inventory: `is_attainable_now`'s `stock_ok`
    short-circuit (already-owned stock needs no acquisition path) is what
    lets an item whose ONLY route is an unbeatable monster's drop still
    surface as a real `near_term_gear` candidate — exactly the "got one lucky
    drop, can never farm a second" shape the real bug needs (an item that
    fails attainability from scratch would never even become a candidate,
    and the starvation bug would be moot). `test_wolf_ears_route_is_
    genuinely_unattainable_from_scratch` below verifies this empirically
    rather than merely asserting it in prose."""
    gd = GameData()
    gd._item_stats = {
        "iron_ring": ItemStats(code="iron_ring", level=1, type_="ring", hp_bonus=1,
                               crafting_skill="jewelrycrafting", crafting_level=1),
        "wolf_ears": ItemStats(code="wolf_ears", level=1, type_="helmet", hp_bonus=100),
    }
    gd._crafting_recipes = {"iron_ring": {"iron_ore": 2}}
    gd._resource_drops = {"iron_rocks": "iron_ore"}
    gd._resource_skill = {"iron_rocks": ("mining", 1)}
    # Somewhere to gather and to craft: the ring must be genuinely craftable.
    gd._resource_locations = {"iron_rocks": [(1, 0)]}
    gd._workshop_locations = {"jewelrycrafting": (0, 1)}
    gd._monster_level = {_UNBEATABLE_MONSTER: 40}
    gd._monster_hp = {_UNBEATABLE_MONSTER: 99999}
    gd._monster_attack = {_UNBEATABLE_MONSTER: {"fire": 9999}}
    fill_monster_stat_defaults(gd)
    gd._monster_drops = {_UNBEATABLE_MONSTER: [("wolf_ears", 10, 1, 1)]}
    gd._monster_locations = {_UNBEATABLE_MONSTER: [(9, 9)]}

    sc = ScenarioCharacter(
        name="ring2_starvation_repro", level=5, max_hp=100,
        equipment={"ring1_slot": "iron_ring"},
        inventory={"wolf_ears": 1},
    )
    state = scenario_state(sc, gd)
    objective = CharacterObjective.from_game_data(gd)
    return state, gd, objective


def test_wolf_ears_route_is_genuinely_unattainable_from_scratch() -> None:
    """Proves the fixture's "genuinely stuck" claim empirically, not just in
    prose: wolf_ears has NO craft recipe, its only dropper is unbeatable at
    this state, and stripped of the one held copy it fails
    `is_attainable_now` outright — the only reason it is a live near_term_gear
    candidate at all is the single already-owned unit (`stock_ok`)."""
    state, gd, _objective = _stuck_wolf_ears_plus_craftable_ring2()
    assert gd.crafting_recipe("wolf_ears") is None
    assert is_winnable(state, gd, _UNBEATABLE_MONSTER) is False
    stripped = replace(state, inventory={})
    assert is_attainable_now("wolf_ears", stripped, gd) is False


_WOLF_EARS = ObtainItem(code="wolf_ears", quantity=1, slot="helmet_slot")
_RING2 = ObtainItem(code="iron_ring", quantity=1, slot="ring2_slot")


def test_without_a_yield_the_stuck_drop_root_heads_every_cycle() -> None:
    """The walk's slot order is history-free, so wolf_ears heads on EVERY
    cycle — the starvation the budget answers — and the craftable ring is its
    FIRST alternative, so a yielded turn goes to the ring."""
    state, gd, objective = _stuck_wolf_ears_plus_craftable_ring2()
    engine = StrategyEngine(objective)
    picks = {engine.decide(state, gd).chosen_root for _ in range(30)}
    assert picks == {_WOLF_EARS}
    assert engine.decide(state, gd).fallback_roots[0] == _RING2

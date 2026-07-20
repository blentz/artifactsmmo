"""Headline regression test for the ring2 arbiter-starvation bug (branch
fix/ring2-arbiter-starvation, docs/superpowers/plans/
2026-07-18-arbiter-focus-aging.md Task 8).

The bug: an achievable craftable gear root (a 2nd `iron_ring` for
`ring2_slot`) starved forever behind a stuck, higher-value, drop-gated root
(`wolf_ears` helmet) — the tree's plain argmax (`gear_target_pick`) always
re-picks the highest-gain candidate every cycle, so a root that can never
actually be COMPLETED (its only source is a monster the character cannot
beat) permanently starves every lower-gain alternative. Tasks 1-7 fixed this
by aging the focused root's selection weight down a deterministic falloff
curve (`falloff`) and handing cycles to reachable alternatives via a
deterministic proportional scheduler (`interleave_due`) once the focused root
has run past `FOCUS_FLAT` cycles.

This test drives the FULL decision path (`StrategyEngine.decide`, which
delegates to `decide_tree`), not the pure cores in isolation — it is the
end-to-end proof that the fix reaches the real arbiter entry point, not just
`progression_tree_core.py`'s unit tests."""

from dataclasses import replace

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, is_attainable_now
from artifactsmmo_cli.ai.tiers.progression_tree_core import FOCUS_FLAT, FOCUS_SPAN
from artifactsmmo_cli.ai.tiers.strategy import StrategyEngine
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai._monster_fixture import fill_monster_stat_defaults

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
        "iron_ring": ItemStats(code="iron_ring", level=1, type_="ring", hp_bonus=1),
        "wolf_ears": ItemStats(code="wolf_ears", level=1, type_="helmet", hp_bonus=100),
    }
    gd._crafting_recipes = {"iron_ring": {"iron_ore": 2}}
    gd._resource_drops = {"iron_rocks": "iron_ore"}
    gd._resource_skill = {"iron_rocks": ("mining", 1)}
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


def test_stuck_drop_root_does_not_starve_the_craftable_second_ring() -> None:
    """The headline fix: over a full falloff window (flat + decay + margin),
    ring2's craftable iron_ring must be chosen at least once — the aging
    hands cycles to it instead of wolf_ears monopolizing forever."""
    state, gd, objective = _stuck_wolf_ears_plus_craftable_ring2()
    engine = StrategyEngine(objective)
    focus: dict[tuple[str, str], int] = {}
    seats: dict[str, int] = {}
    chosen_ring2 = False
    for _ in range(FOCUS_FLAT + FOCUS_SPAN + 20):
        # mirror the player: the focus ledger AND the incremental d'Hondt seat
        # accumulator (Task 12) both drive the aging pick.
        d = engine.decide(state, gd, band_adequate=False, focus=focus, seats=seats)
        key = ("ring2_slot", "iron_ring")
        wk = ("helmet_slot", "wolf_ears")
        chosen = repr(d.chosen_root)
        if "ring2_slot" in chosen:
            chosen_ring2 = True
        # simulate the ledger + seat bump the player does after every cycle:
        # focus bumps every committed cycle; the d'Hondt seat bumps only when
        # THIS decision's gear pick went through the interleave (d.aged_pick),
        # keyed by the committed slot (mirrors GamePlayer._bump_focus, Task 12).
        if "helmet_slot" in chosen:
            focus[wk] = focus.get(wk, 0) + 1
            if d.aged_pick:
                seats["helmet_slot"] = seats.get("helmet_slot", 0) + 1
        elif "ring2_slot" in chosen:
            focus[key] = focus.get(key, 0) + 1
            if d.aged_pick:
                seats["ring2_slot"] = seats.get("ring2_slot", 0) + 1
    assert chosen_ring2, "ring2 iron_ring was never chosen — still starved"


def test_pre_fix_behavior_absent_aging_would_starve() -> None:
    """Sanity: with focus frozen EMPTY every cycle (aging never engages —
    `focus_aging_pick` is bit-identical to the plain `gear_target_pick`
    argmax whenever every candidate's own focus level is 0), the argmax picks
    wolf_ears on EVERY cycle and ring2's iron_ring is NEVER chosen — this is
    exactly the starvation the aging (Tasks 1-7) fixes."""
    state, gd, objective = _stuck_wolf_ears_plus_craftable_ring2()
    engine = StrategyEngine(objective)
    picks = {repr(engine.decide(state, gd, band_adequate=False, focus={}, seats={}).chosen_root)
             for _ in range(30)}
    assert picks == {"ObtainItem(code='wolf_ears', quantity=1, slot='helmet_slot')"}

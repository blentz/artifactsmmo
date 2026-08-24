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
`progression_tree_core.py`'s unit tests.

WAVE 3a REMOVED THAT FIX FROM THIS PATH. `decide_tree` no longer takes a focus
ledger or a seat accumulator, so the aging cannot engage through
`StrategyEngine.decide` at all. The two tests that proved it did are gone and
`test_wave3a_walk_re_exhibits_the_starvation_this_file_was_written_for` stands
in their place, pinning what the walk actually does now. Read that test's
docstring before treating this file as green."""

from dataclasses import replace
from pathlib import Path

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import (
    SCENARIOS,
    ScenarioCharacter,
    load_bundle_game_data,
    scenario_state,
)
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, is_attainable_now
from artifactsmmo_cli.ai.tiers.progression_tree_core import FOCUS_FLAT, FOCUS_SPAN
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
    """THE HEADLINE FIX, restored. Over a full falloff window (flat + decay +
    margin) ring2's craftable iron_ring must be chosen at least once: the
    aging hands cycles to it instead of wolf_ears monopolising forever.

    RE-ROUTED BY WAVE 3a fix-round 1. The ledger no longer rides two
    `decide()` parameters; it rides `SelectionContext`, the same seam
    `supply_target` uses, and the walk reads it in
    `WhichSlotIsFurthestBehind`. The loop below is otherwise the one that
    stood here before the flip: bump focus for the committed slot every cycle,
    bump a d'Hondt seat only on an INTERLEAVED decision (`aged_pick`), exactly
    as `GamePlayer._charge_focus` does.

    Why the flip broke it and why servability does not cover it: `_slot_order`
    is a pure, history-free total order over a target set that does not change
    while the character makes no progress, and `_servable_promotion` only
    demotes a root the planner CANNOT SERVE — wolf_ears is held, so its
    `UpgradeEquipment` plans every cycle and never completes. Nothing but
    aging rotates off it.

    FIX-ROUND 2: the loop CALLS `GamePlayer._gear_root_key` and
    `._focus_key_str` instead of hand-rolling
    `("ring2_slot", "iron_ring") if … else …`. The hand-rolled version returned
    what the real collaborator returns ONLY for this fixture's two slotted
    `ObtainItem` roots, so it passed while the production key was answering
    None for every skill-gated and material-gated root the walk can name — the
    ledger stayed empty live and this test could not see it. Decorative
    mechanism 5, in the pin written to prevent exactly this class of miss."""
    state, gd, objective = _stuck_wolf_ears_plus_craftable_ring2()
    engine = StrategyEngine(objective)
    focus: dict[tuple[str, str], int] = {}
    seats: dict[str, int] = {}
    chosen_ring2 = False
    for _ in range(FOCUS_FLAT + FOCUS_SPAN + 20):
        ctx = replace(NO_PROFILE_CONTEXT, gear_focus=focus, interleave_seats=seats)
        d = engine.decide(state, gd, ctx=ctx)
        if "ring2_slot" in repr(d.chosen_root):
            chosen_ring2 = True
        # EXACTLY `GamePlayer._charge_focus`, through the production key.
        key = GamePlayer._gear_root_key(d.chosen_root)
        assert key is not None, (
            "the committed root must carry a ledger key, or nothing ages: "
            f"{d.chosen_root!r}")
        focus[key] = focus.get(key, 0) + 1
        if d.aged_pick:
            seat = GamePlayer._focus_key_str(key)
            seats[seat] = seats.get(seat, 0) + 1
    assert chosen_ring2, "ring2 iron_ring was never chosen — still starved"


def test_a_skill_gated_head_carries_a_ledger_key_and_rotates() -> None:
    """THE ROOT SHAPE THE FLIP INTRODUCED AND FIX-ROUND 1 COULD NOT AGE.

    `IsThisTargetBlocked`'s skill arm returns `ReachSkillLevel`, which has
    neither `.slot` nor `.code`; the material arm returns `ObtainItem` with
    `slot=None`. The old `_gear_root_key` duck-typed both to None, so
    `_charge_focus` returned early — no focus entry AND no d'Hondt seat — and
    the ledger stayed permanently empty. Measured over 130 charged cycles on
    `l10_weapon_upgrade`: one distinct root, `ledger: {}`. The skill-climb root
    this whole epic exists to produce was precisely the one that could not
    rotate.

    Driven through `GamePlayer._gear_root_key` for the same reason the test
    above now is: a hand-rolled key would pass whatever the production one
    does."""
    gd = load_bundle_game_data(BUNDLE)
    state = scenario_state(SCENARIOS["l10_weapon_upgrade"], gd)
    engine = StrategyEngine(CharacterObjective.from_game_data(gd))

    first = engine.decide(state, gd)
    assert first.chosen_root == ReachSkillLevel(skill="jewelrycrafting", level=2)
    assert GamePlayer._gear_root_key(first.chosen_root) is not None, (
        "a skill-gated head must key, or it can never age")

    focus: dict[tuple[str, str], int] = {}
    seats: dict[str, int] = {}
    seen: set[str] = set()
    for _ in range(FOCUS_FLAT + FOCUS_SPAN + 20):
        ctx = replace(NO_PROFILE_CONTEXT, gear_focus=focus, interleave_seats=seats)
        d = engine.decide(state, gd, ctx=ctx)
        seen.add(repr(d.chosen_root))
        key = GamePlayer._gear_root_key(d.chosen_root)
        assert key is not None, (
            f"the committed root must carry a ledger key: {d.chosen_root!r}")
        focus[key] = focus.get(key, 0) + 1
        if d.aged_pick:
            seat = GamePlayer._focus_key_str(key)
            seats[seat] = seats.get(seat, 0) + 1
    assert focus, "the ledger never filled — nothing was charged"
    assert len(seen) > 1, (
        f"the skill-climb head never rotated over a full falloff window: {seen}")


def test_absent_aging_the_stuck_drop_root_would_starve() -> None:
    """The non-vacuity twin: with the ledger frozen EMPTY every cycle the walk
    takes its unaged fast path — `_slot_order`'s argmax, bit-identical to the
    history-free order — and wolf_ears wins on EVERY cycle. Without this, the
    test above could pass because the walk had become nondeterministic rather
    than because the aging engaged."""
    state, gd, objective = _stuck_wolf_ears_plus_craftable_ring2()
    engine = StrategyEngine(objective)
    picks = {repr(engine.decide(state, gd).chosen_root) for _ in range(30)}
    assert picks == {"ObtainItem(code='wolf_ears', quantity=1, slot='helmet_slot')"}
    assert ObtainItem(code="iron_ring", quantity=1, slot="ring2_slot") in \
        engine.decide(state, gd).fallback_roots

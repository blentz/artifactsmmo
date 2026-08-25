"""Bag pressure against bank state — coverage-matrix cells 8 and 9.

Twenty-six of the thirty committed scenarios carried an EMPTY bag against 0 of
80,194 live cycles, and the consequence was a guard ladder nobody could reach:
`CRAFT_RELIEF`, `RECYCLE_RELIEF` and `SELL_RELIEF` fired in 0/36 scenarios.

The two cells are the same dimension pair (D6 bag pressure x D7 bank state) at
opposite corners, and they are opposite on BOTH axes on purpose:

| cell | quantity frac | slot frac | bank | guards it reaches |
|---|---|---|---|---|
| 8 `l20_relief_full_bank`        | 0.59 | **0.80** | FULL  | CRAFT/RECYCLE/SELL_RELIEF |
| 9 `l20_bag_critical_empty_bank` | **0.95** | 0.25 | EMPTY | DISCARD_CRITICAL, DEPOSIT_FULL |

The split matters because the ladder reads TWO different measures.
`_used_fraction` (the SPACE measure, max of quantity and slot) drives the
relief guards and DEPOSIT_FULL; `_quantity_fraction` drives both DISCARD
guards. Cell 8 puts pressure only on the slot axis, which is the live Robby
2026-07-10 shape (20/20 slots at 76/124 quantity) and is exactly what keeps the
DISCARD guards — which would PREEMPT — off the cell that is testing relief.

`bank_has_room` is `len(bank_items) < game_data.bank_capacity`, so "stocked"
has to mean "as many distinct codes as the bank has slots". Cell 8's bank
carries exactly that; cell 9's is empty, which is what puts DEPOSIT_FULL up.

Cell 8 also declares `timber_merchant` active. Every item-buying NPC in this
game is an event NPC, so outside a window `sellable_tradeable_now` is False by
construction and SELL_RELIEF could not fire for any bag at all.
"""

import dataclasses

import pytest

from artifactsmmo_cli.ai.bank_room import bank_has_room
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.thresholds import (
    CRAFT_RELIEF_FRACTION,
    DEPOSIT_FULL_FRACTION,
    PRESSURE_CRITICAL_FRACTION,
    PRESSURE_HIGH_FRACTION,
)
from artifactsmmo_cli.ai.tiers.guards import GuardKind, active_guards
from artifactsmmo_cli.ai.world_state import WorldState

RELIEF_CELL = "l20_relief_full_bank"
CRITICAL_CELL = "l20_bag_critical_empty_bank"

RELIEF_GUARDS = frozenset({GuardKind.CRAFT_RELIEF, GuardKind.RECYCLE_RELIEF,
                           GuardKind.SELL_RELIEF})
CRITICAL_GUARDS = frozenset({GuardKind.DISCARD_CRITICAL, GuardKind.DEPOSIT_FULL})


def _state(name: str, game_data: GameData) -> WorldState:
    return scenario_state(SCENARIOS[name], game_data)


def _fired(state: WorldState, game_data: GameData) -> frozenset[GuardKind]:
    return frozenset(active_guards(state, game_data, None, NO_PROFILE_CONTEXT))


def _quantity_fraction(state: WorldState) -> float:
    return state.inventory_used / state.inventory_max


def _slot_fraction(state: WorldState) -> float:
    return state.inventory_slots_used / state.inventory_slots_max


# --- cell 8: relief under a bank with no room -------------------------------

def test_cell8_pressure_is_on_the_slot_axis_only(
        bundle_game_data: GameData) -> None:
    """The premise, and the masking argument in one place.

    Slot pressure clears CRAFT_RELIEF's watermark; quantity pressure stays
    below BOTH discard watermarks, so nothing higher in `GUARD_ORDER` can
    preempt the guards this cell exists to reach (design §5.2)."""
    state = _state(RELIEF_CELL, bundle_game_data)
    assert _slot_fraction(state) >= CRAFT_RELIEF_FRACTION
    assert _quantity_fraction(state) < PRESSURE_HIGH_FRACTION
    assert _quantity_fraction(state) < PRESSURE_CRITICAL_FRACTION


def test_cell8_bank_is_stocked_to_capacity(bundle_game_data: GameData) -> None:
    """"Stocked" is not decoration: RECYCLE_RELIEF and SELL_RELIEF both open
    with `not bank_has_room(...)`, so a bank one code short of capacity would
    silently turn this cell into a DEPOSIT_FULL cell."""
    state = _state(RELIEF_CELL, bundle_game_data)
    assert state.bank_items is not None
    assert len(state.bank_items) == bundle_game_data.bank_capacity
    assert not bank_has_room(True, state.bank_items,
                             bundle_game_data.bank_capacity)


def test_cell8_fires_all_three_relief_guards(
        bundle_game_data: GameData) -> None:
    """The three guards that fired in 0/36 scenarios, all up at once — and
    DEPOSIT_FULL absent, because the bank it would deposit into is full."""
    fired = _fired(_state(RELIEF_CELL, bundle_game_data), bundle_game_data)
    assert fired >= RELIEF_GUARDS
    assert GuardKind.DEPOSIT_FULL not in fired
    assert GuardKind.DISCARD_HIGH not in fired
    assert GuardKind.DISCARD_CRITICAL not in fired


@pytest.mark.parametrize(
    ("field", "value", "silenced"),
    [
        ("bank", {},
         frozenset({GuardKind.RECYCLE_RELIEF, GuardKind.SELL_RELIEF})),
        ("active_events", (), frozenset({GuardKind.SELL_RELIEF})),
        ("inventory_slots_max", 200, frozenset({GuardKind.CRAFT_RELIEF})),
    ],
)
def test_cell8_each_axis_silences_exactly_the_guards_it_owns(
        bundle_game_data: GameData, field: str, value: object,
        silenced: frozenset[GuardKind]) -> None:
    """Proof it bites, one axis at a time.

    Emptying the bank kills the two bank-full guards and nothing else; closing
    the buyer window kills only SELL_RELIEF; relieving the slot cap kills only
    CRAFT_RELIEF. Three flips, three disjoint answers — so no guard here is
    firing for a reason the cell did not declare."""
    flipped = scenario_state(
        dataclasses.replace(SCENARIOS[RELIEF_CELL], **{field: value}),
        bundle_game_data)
    fired = _fired(flipped, bundle_game_data)
    assert RELIEF_GUARDS - fired == silenced


def test_cell8_reaches_a_relief_goal_end_to_end(
        bundle_game_data: GameData) -> None:
    """The flip reaches a DECISION, not just a predicate: the arbiter selects
    the craft-relief goal and plans the craft that frees the slot."""
    state = _state(RELIEF_CELL, bundle_game_data)
    player = GamePlayer(character=RELIEF_CELL, history=None)
    player.seed_offline(state, bundle_game_data)
    report = player.plan_from_state()
    assert repr(report.selected_goal) == "CraftRelief(copper_bar)"
    assert report.plan and "Craft(copper_bar" in repr(report.plan[0])


# --- cell 9: critical quantity against a bank with room ---------------------

def test_cell9_pressure_is_on_the_quantity_axis_only(
        bundle_game_data: GameData) -> None:
    """The mirror of cell 8's premise: quantity clears the CRITICAL watermark
    (and therefore DEPOSIT_FULL's, which reads the max of the two), while only
    a quarter of the slots are used."""
    state = _state(CRITICAL_CELL, bundle_game_data)
    assert _quantity_fraction(state) >= PRESSURE_CRITICAL_FRACTION
    assert _quantity_fraction(state) >= DEPOSIT_FULL_FRACTION
    assert _slot_fraction(state) < CRAFT_RELIEF_FRACTION


def test_cell9_fires_discard_critical_and_deposit_full(
        bundle_game_data: GameData) -> None:
    """The pair §5.3 names, up together — which needs the bank to have room
    (DEPOSIT_FULL) while the bag is over the destruction watermark."""
    state = _state(CRITICAL_CELL, bundle_game_data)
    assert state.bank_items == {}
    assert bank_has_room(True, state.bank_items, bundle_game_data.bank_capacity)
    assert _fired(state, bundle_game_data) >= CRITICAL_GUARDS


@pytest.mark.parametrize(
    ("field", "value", "silenced"),
    [
        ("inventory", None, frozenset({GuardKind.DISCARD_CRITICAL})),
        ("bank", None, frozenset({GuardKind.DEPOSIT_FULL})),
    ],
)
def test_cell9_each_axis_silences_exactly_the_guard_it_owns(
        bundle_game_data: GameData, field: str, value: object,
        silenced: frozenset[GuardKind]) -> None:
    """Proof it bites, again one axis at a time.

    Four fewer `sap` takes the QUANTITY fraction from 0.950 to 0.925 — below
    DISCARD_CRITICAL's rung, still above DEPOSIT_FULL's — and only
    DISCARD_CRITICAL goes quiet. Filling the BANK to capacity leaves the bag
    untouched and only DEPOSIT_FULL goes quiet. Neither flip disturbs the
    other guard, so each is answering its own axis."""
    scenario = SCENARIOS[CRITICAL_CELL]
    if field == "inventory":
        replacement: object = {**scenario.inventory, "sap": 38}
    else:
        replacement = dict.fromkeys(
            sorted(SCENARIOS[RELIEF_CELL].bank or {}), 1)
    flipped = scenario_state(
        dataclasses.replace(scenario, **{field: replacement}), bundle_game_data)
    fired = _fired(flipped, bundle_game_data)
    assert CRITICAL_GUARDS - fired == silenced


def test_cell9_reaches_the_discard_goal_end_to_end(
        bundle_game_data: GameData) -> None:
    """DISCARD_CRITICAL sits above DEPOSIT_FULL in `GUARD_ORDER`, so the
    selected goal is the shed — asserted so a ladder reorder is visible here
    rather than only in the ladder's own tests."""
    state = _state(CRITICAL_CELL, bundle_game_data)
    player = GamePlayer(character=CRITICAL_CELL, history=None)
    player.seed_offline(state, bundle_game_data)
    report = player.plan_from_state()
    assert repr(report.selected_goal) == "DiscardOverstock"


# --- the gap these two cells close ------------------------------------------

def test_no_other_scenario_reaches_any_of_these_five_guards(
        bundle_game_data: GameData) -> None:
    """The measurement that makes both cells worth their runtime.

    The three relief guards fired NOWHERE before cell 8. DISCARD_CRITICAL and
    DEPOSIT_FULL each had exactly one witness (`l8_overstocked`), and neither
    had one against the OTHER side of the bank dimension — which is the pair
    cell 9 adds. Written as an equality over scenario names so a future cell
    that also fires them updates this list deliberately."""
    holders: dict[GuardKind, set[str]] = {
        kind: set() for kind in RELIEF_GUARDS | CRITICAL_GUARDS}
    for name in SCENARIOS:
        fired = _fired(_state(name, bundle_game_data), bundle_game_data)
        for kind in holders:
            if kind in fired:
                holders[kind].add(name)
    assert holders[GuardKind.CRAFT_RELIEF] == {RELIEF_CELL}
    assert holders[GuardKind.RECYCLE_RELIEF] == {RELIEF_CELL}
    assert holders[GuardKind.SELL_RELIEF] == {RELIEF_CELL}
    assert holders[GuardKind.DISCARD_CRITICAL] == {"l8_overstocked",
                                                   CRITICAL_CELL}
    assert holders[GuardKind.DEPOSIT_FULL] == {"l8_overstocked", CRITICAL_CELL}

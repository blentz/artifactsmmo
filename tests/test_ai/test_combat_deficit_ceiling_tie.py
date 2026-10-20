"""What decides a `combat_deficit` pick once every candidate hits the CEILING.

`acquisition_cost_core._capped` (325abf5d) holds every answer at
`UNOBTAINABLE_PER_UNIT * units`, because an unaffordable-but-real route used to
price at `price * 10**6 + 2` and so ranked BELOW a route that does not exist.
The fix is right and the collapse it creates is deliberate: an unaffordable route
and a nonexistent one now price IDENTICALLY, so nothing ranking on this number
can tell them apart. Its own report said so, and said the tie's sanity rested on
a downstream property verified BY READING and not by a test:

    "a future consumer using `>=` or an order-dependent scan would decide it by
    iteration order."

This file is that test. The claim being pinned is `combat_deficit`'s: with every
candidate at the ceiling the score `gain / cost` has a common denominator, so the
winner is the one with the largest RAW MARGIN GAIN, and only a further tie in the
gain itself falls through to `_pool` order — which is `game_data.items.stats`
insertion order, i.e. the server's items pages.

THE TIE IS NOT A FIXTURE ARTEFACT, and that is the whole point of driving the
committed real-catalogue bundle rather than a hand-built `GameData`. Swept
(2026-10-17, after the barrier refresh model) over every committed scenario x
every monster that scenario's margin is negative against, pricing with the
production `acquisition_actions(..., equip=True)`:

  * 579 (scenario, monster) pairs where EVERY margin-improving candidate prices
    at the ceiling — so `gain / cost` has one denominator and the cost key is
    inert.
  * 21 of those 579 where every candidate's GAIN is tied as well (two or more
    candidates), leaving `_pool` order as the sole decider with nothing semantic
    under it.

The two cases pinned below are drawn from that sweep:

  * `l24_fisher_cooking_rung` vs `king_slime` — 8 improving candidates, all 8
    at the ceiling, two sharing the top gain of 61. Gain decides.
  * `l47_depth3_amulet` vs `sandwarden` — 5 improving candidates, all 5 at the
    ceiling, all 5 gaining exactly 1. Catalogue order decides.

At `l20_band_entry`, 98 of the 108 equippables at or below the character's level
price at the ceiling. This is the common case, not the corner.
"""

import dataclasses
from collections.abc import Callable
from functools import cache
from itertools import pairwise
from pathlib import Path

from artifactsmmo_cli.ai.acquisition_cost import EQUIP_ACTIONS, acquisition_actions
from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.combat import combat_margin
from artifactsmmo_cli.ai.combat_deficit import combat_deficit
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_taxonomy import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.scenario import (
    SCENARIOS,
    load_bundle_game_data,
    scenario_state,
)
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"

CEILING = UNOBTAINABLE_PER_UNIT + EQUIP_ACTIONS
"""What `acquisition_actions(..., equip=True)` returns for a capped answer.

`EQUIP_ACTIONS` is added by the wrapper AFTER `_capped`, so the ceiling a
`actions_of` consumer actually sees is one action above the cap. It is a constant
per call site — `deficit_upgrade_target`'s pricer passes `equip=True` for every
candidate — so it shifts the whole tied set and cannot reorder it.
"""


@cache
def _gd() -> GameData:
    """The committed real-catalogue bundle. Quiet market, as every other
    scenario test takes it — a populated order book is a declared world
    property, never a default (`GameData.from_cache_bundle`)."""
    return load_bundle_game_data(BUNDLE)


def _rested(name: str) -> WorldState:
    """A scenario character at restorable hp — the state `combat_deficit`
    evaluates internally, hoisted so the assertions below can price against
    exactly what the walk prices against."""
    state = scenario_state(SCENARIOS[name], _gd())
    return dataclasses.replace(state, hp=state.max_hp)


def _priced_improvers(
    state: WorldState, monster: str,
) -> list[tuple[int, str, int, int]]:
    """`(catalogue_index, code, margin_gain, cost)` for every default-pool
    candidate that improves the margin — the exact set `combat_deficit`'s first
    greedy step ranks, computed the same way it computes it."""
    gd = _gd()
    order = list(gd.items.stats)
    base = combat_margin(state, gd, monster)
    rows = []
    for code, stats in gd.items.stats.items():
        if stats.type_ not in ITEM_TYPE_TO_SLOTS or stats.level > state.level:
            continue
        trial = dict(state.inventory)
        trial[code] = trial.get(code, 0) + 1
        margin = combat_margin(dataclasses.replace(state, inventory=trial),
                               gd, monster)
        if margin <= base:
            continue
        rows.append((order.index(code), code, margin - base,
                     acquisition_actions(code, 1, state, gd,
                                         TIMED_NO_PROFILE_CONTEXT, equip=True)))
    return sorted(rows)


def _actions_of(state: WorldState) -> Callable[[str, str], int]:
    """The production pricer, exactly as `strategy_driver`'s GEAR_REVIEW branch
    and the `combat-deficit` diagnostic build it."""
    def priced(code: str, slot: str) -> int:
        return acquisition_actions(code, 1, state, _gd(),
                                   TIMED_NO_PROFILE_CONTEXT, equip=slot is not None)
    return priced


def test_at_the_ceiling_the_winner_is_the_largest_raw_margin_gain() -> None:
    """Every candidate ties on cost, so the largest GAIN wins — not the first.

    `l24_fisher_cooking_rung` vs `king_slime`, real catalogue: all 8 improving
    candidates price at the ceiling, so `gain / cost` shares a denominator and
    collapses to `gain`. Four candidates sit EARLIER in catalogue order than
    the winner and every one of them loses, which is what separates "gain
    decides" from "iteration order decides".
    """
    state = _rested("l24_fisher_cooking_rung")
    rows = _priced_improvers(state, "king_slime")

    # The tie is real and TOTAL: nothing here has a route the character can pay
    # for, so the cap is what every one of these numbers is.
    assert len(rows) == 8
    assert {cost for _i, _c, _g, cost in rows} == {CEILING}

    top = max(gain for _i, _c, gain, _cost in rows)
    winners = [code for _i, code, gain, _cost in rows if gain == top]
    assert top == 61
    assert winners == ["skull_staff", "steel_battleaxe"]
    # Four earlier-in-catalogue candidates, all beaten on gain alone.
    first_winner_index = min(i for i, _c, gain, _cost in rows if gain == top)
    assert sum(1 for i, _c, _g, _cost in rows if i < first_winner_index) == 4

    deficit = combat_deficit(state, _gd(), "king_slime", max_chain=1,
                             actions_of=_actions_of(state))

    assert deficit is not None
    assert [s.code for s in deficit.chain] == ["skull_staff"]
    assert deficit.chain[0].acquire_cost == float(CEILING)


def test_a_gain_tie_at_the_ceiling_falls_to_catalogue_order_and_takes_the_first() -> None:
    """When the GAIN ties too, `_pool` order decides — and it takes the FIRST.

    `l47_depth3_amulet` vs `sandwarden`, real catalogue: 5 candidates improve
    the margin, all 5 at the ceiling, all 5 by exactly +1. Nothing semantic is
    left, so the answer is `game_data.items.stats` insertion order — the server's
    items pages — and the walk's strict `score > best_score` keeps the incumbent,
    which is the earliest of them.

    Recorded honestly rather than defended: this is an INCIDENTAL key. It is
    ACCEPTABLE today only because the bundle's item pages are level-monotone (0
    descending steps across all 522 items), so "first in the catalogue" is
    currently "lowest item level" — the level-40 `mithril_ring` ahead of the
    level-45 `diabolic_elixir`. Nothing in the code says that, and a server that
    reorders its pages changes this ranking with no diff. See
    `.superpowers/sdd/PLAN_wave3b_deletion/pricing-tiebreak-audit-report.md`
    for the proposed semantic key.

    It pins `combat_deficit`'s RANKING and nothing further. (This pair used to
    be `dusk_beetle`, whose nine amulets tied at +1 while the model charged its
    barrier once; refreshed every 5 turns, the barrier makes some candidates
    gain 2 and prices some below the ceiling, so the tie is gone there.)
    """
    state = _rested("l47_depth3_amulet")
    rows = _priced_improvers(state, "sandwarden")

    assert len(rows) == 5
    assert {cost for _i, _c, _g, cost in rows} == {CEILING}
    assert {gain for _i, _c, gain, _cost in rows} == {1}

    by_catalogue = [code for _i, code, _g, _cost in rows]
    assert by_catalogue[0] == "mithril_ring"
    assert by_catalogue[-1] == "diabolic_elixir"

    deficit = combat_deficit(state, _gd(), "sandwarden", max_chain=1,
                             actions_of=_actions_of(state))

    assert deficit is not None
    assert [s.code for s in deficit.chain] == ["mithril_ring"]


def test_the_dusk_beetle_chain_closes_only_with_a_lifesteal_rune() -> None:
    """A margin walk that stalls closes on the bare odds, at depth 3.

    `l47_depth3_amulet` vs `dusk_beetle` on the real catalogue: the margin is -8
    and the margin walk stalls at -5 — a `water_boost_potion` and a
    `greater_sapphire_amulet`, after which nothing on offer moves the number.
    The stall falls back to the bare odds, and `greater_lifesteal_rune` lifts
    them past the bar: a lifesteal heals its share of the crit's DAMAGE
    (server logs 2026-10-17), not of the attack stat, which made every rune
    worth half of what it is. Until then this pair closed at no depth. (Its
    barrier, refreshed every 5 turns since 2026-10-17, moved the margin from -6
    to -8 and the first two steps; the rune still closes it at depth 3.)

    Also pinned: the answer does not move with the bound. The walk is greedy and
    prefix-stable, which is what lets `deficit_upgrade_target` pay for `closes`
    with depth without changing which item it targets.
    """
    state = _rested("l47_depth3_amulet")

    by_depth = {
        depth: combat_deficit(state, _gd(), "dusk_beetle", max_chain=depth,
                              actions_of=_actions_of(state))
        for depth in (1, 2, 3, 8)
    }

    assert all(d is not None for d in by_depth.values())
    assert {d.baseline_margin for d in by_depth.values() if d is not None} == {-8}
    # It closes once the walk may take the rune, and not before.
    assert {depth: d.closes for depth, d in by_depth.items() if d is not None} == {
        1: False, 2: False, 3: True, 8: True}
    deepest = by_depth[8]
    assert deepest is not None
    assert [s.code for s in deepest.chain] == ["water_boost_potion", "greater_sapphire_amulet",
                                              "greater_lifesteal_rune"]
    assert [s.margin_after for s in deepest.chain] == [-7, -5, -5]
    # Prefix stability: every shallower chain is a prefix of the deepest one.
    for depth, deficit in by_depth.items():
        assert deficit is not None
        assert [s.code for s in deficit.chain] == [
            s.code for s in deepest.chain][:len(deficit.chain)], depth


def test_the_catalogue_is_level_monotone_which_is_why_that_order_reads_sane() -> None:
    """The premise the test above leans on, pinned so it cannot rot silently.

    If a future bundle capture stops being level-monotone, the incidental
    tiebreak stops correlating with anything semantic and this fails — which is
    the notice that the semantic key is now owed rather than merely proposed.
    """
    levels = [stats.level for stats in _gd().items.stats.values()]

    assert len(levels) == 522
    assert sum(1 for a, b in pairwise(levels) if b < a) == 0

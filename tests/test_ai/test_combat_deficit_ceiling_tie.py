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
committed real-catalogue bundle rather than a hand-built `GameData`. Swept over
every committed scenario x every monster that scenario loses to, pricing with the
production `acquisition_actions(..., equip=True)`:

  * 249 (scenario, monster) pairs where EVERY margin-improving candidate prices
    at the ceiling — so `gain / cost` has one denominator and the cost key is
    inert.
  * 75 of those 249 where the top GAIN is tied as well, leaving `_pool` order as
    the sole decider with nothing semantic under it.
  * 49 further pairs where the ceiling-tied top-gain set has more than one member
    even though some cheaper candidate exists.

The two cases pinned below are drawn from that sweep:

  * `l24_fisher_cooking_rung` vs `king_slime` — 23 improving candidates, all 23
    at the ceiling, two sharing the top gain of 18. Gain decides.
  * `l47_depth3_amulet` vs `dusk_beetle` — 9 improving candidates, all 9 at the
    ceiling, all 9 gaining exactly 1. Catalogue order decides.

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
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.world_state import WorldState

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
                                         NO_PROFILE_CONTEXT, equip=True)))
    return sorted(rows)


def _actions_of(state: WorldState) -> Callable[[str, str], int]:
    """The production pricer, exactly as `strategy_driver`'s GEAR_REVIEW branch
    and the `combat-deficit` diagnostic build it."""
    def priced(code: str, slot: str) -> int:
        return acquisition_actions(code, 1, state, _gd(),
                                   NO_PROFILE_CONTEXT, equip=slot is not None)
    return priced


def test_at_the_ceiling_the_winner_is_the_largest_raw_margin_gain() -> None:
    """Every candidate ties on cost, so the largest GAIN wins — not the first.

    `l24_fisher_cooking_rung` vs `king_slime`, real catalogue: all 23 improving
    candidates price at the ceiling, so `gain / cost` shares a denominator and
    collapses to `gain`. Fifteen candidates sit EARLIER in catalogue order than
    the winner and every one of them loses, which is what separates "gain
    decides" from "iteration order decides".
    """
    state = _rested("l24_fisher_cooking_rung")
    rows = _priced_improvers(state, "king_slime")

    # The tie is real and TOTAL: nothing here has a route the character can pay
    # for, so the cap is what every one of these numbers is.
    assert len(rows) == 23
    assert {cost for _i, _c, _g, cost in rows} == {CEILING}

    top = max(gain for _i, _c, gain, _cost in rows)
    winners = [code for _i, code, gain, _cost in rows if gain == top]
    assert top == 18
    assert winners == ["skull_staff", "steel_battleaxe"]
    # Fifteen earlier-in-catalogue candidates, all beaten on gain alone.
    first_winner_index = min(i for i, _c, gain, _cost in rows if gain == top)
    assert sum(1 for i, _c, _g, _cost in rows if i < first_winner_index) == 15

    deficit = combat_deficit(state, _gd(), "king_slime", max_chain=1,
                             actions_of=_actions_of(state))

    assert deficit is not None
    assert [s.code for s in deficit.chain] == ["skull_staff"]
    assert deficit.chain[0].acquire_cost == float(CEILING)


def test_a_gain_tie_at_the_ceiling_falls_to_catalogue_order_and_takes_the_first() -> None:
    """When the GAIN ties too, `_pool` order decides — and it takes the FIRST.

    `l47_depth3_amulet` vs `dusk_beetle`, real catalogue: 9 candidates improve
    the margin, all 9 at the ceiling, all 9 by exactly +1. Nothing semantic is
    left, so the answer is `game_data.items.stats` insertion order — the server's
    items pages — and the walk's strict `score > best_score` keeps the incumbent,
    which is the earliest of them.

    Recorded honestly rather than defended: this is an INCIDENTAL key. It is
    ACCEPTABLE today only because the bundle's item pages are level-monotone (0
    descending steps across all 522 items), so "first in the catalogue" is
    currently "lowest item level" — `emerald_amulet` at level 25 over
    `greater_emerald_amulet` at level 40. Nothing in the code says that, and a
    server that reorders its pages changes this ranking with no diff. See
    `.superpowers/sdd/PLAN_wave3b_deletion/pricing-tiebreak-audit-report.md`
    for the proposed semantic key.

    WHAT THIS TEST IS NOW, AND IS NOT. It pins `combat_deficit`'s RANKING and
    nothing further. It is not vacuous — the nine candidates still tie, and the
    strict `>` still takes the first — but the decision it once appeared to
    describe is gone: `deficit_upgrade_target` reads `closes`, and this pair
    never closes at any depth (see the test below), so the tie decides nothing a
    character acts on. That is also the answer to the level-25-for-a-level-47
    objection this pair provoked: it was never a tie-break defect. Both the
    lower-level key the audit proposed and the higher-level key intuition
    suggests would have picked among nine items that cannot win the fight.
    """
    state = _rested("l47_depth3_amulet")
    rows = _priced_improvers(state, "dusk_beetle")

    assert len(rows) == 9
    assert {cost for _i, _c, _g, cost in rows} == {CEILING}
    assert {gain for _i, _c, gain, _cost in rows} == {1}

    by_catalogue = [code for _i, code, _g, _cost in rows]
    assert by_catalogue[0] == "emerald_amulet"
    assert "greater_emerald_amulet" in by_catalogue

    deficit = combat_deficit(state, _gd(), "dusk_beetle", max_chain=1,
                             actions_of=_actions_of(state))

    assert deficit is not None
    assert [s.code for s in deficit.chain] == ["emerald_amulet"]


def test_the_tied_amulet_pick_closes_nothing_at_any_depth() -> None:
    """Why the level-25-amulet objection is a FUTILITY finding, not a tie finding.

    `l47_depth3_amulet` vs `dusk_beetle` on the real catalogue: the margin is -6
    and the best chain the walk can assemble at ANY bound reaches -4 — one
    amulet and one `enhanced_boost_potion`, after which nothing on offer moves
    the number at all. So the ranking among the nine tied +1 candidates decides
    which futile item gets named in a diagnostic, and nothing else. There is no
    quality floor to add here and no level-aware key that would have helped:
    every candidate in the set is equally unable to win this fight, whatever its
    level.

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
    assert {d.baseline_margin for d in by_depth.values() if d is not None} == {-6}
    # Nothing closes, at any bound the walk is allowed.
    assert not any(d.closes for d in by_depth.values() if d is not None)
    deepest = by_depth[8]
    assert deepest is not None
    assert [s.code for s in deepest.chain] == ["emerald_amulet",
                                              "enhanced_boost_potion"]
    assert deepest.chain[-1].margin_after == -4
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

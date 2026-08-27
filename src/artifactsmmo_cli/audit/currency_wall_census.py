"""O7 — every currency gap on an active link is FUNDED or NAMED.

Obligation O7 of the wave-6 routes design (§7). For every `(scenario, currency)`
cell: if the price walk charged that currency at `UNOBTAINABLE_PER_UNIT` while
pricing the scenario's resolved root, the currency must either be task-earnable
(a funding route exists, and `ReachCurrencyGoal` is the node that takes it) or
fall into a NAMED wall. A charged currency that is neither is
`o7_silent_currency_stall` — a root the graph resolved to, priced at a million,
with nothing in the model saying why.

HOW A CHARGE IS DETECTED, AND WHY NOT BY WALKING THE CLOSURE. The pricer does
not report which code it walled on. Re-deriving the demand closure here to find
out would be a SECOND implementation of the cost model — precisely what
obligation O6 forbids, and the drift it forbids it for. So the census asks
production's own pricer a differential question instead: price the root as it
stands, then price it again with the currency granted into the bag. A price that
FALLS when the currency is held is a price that was paying an unobtainable
charge for it. One pricer, no second walk, and the detector is pinned by
positive controls in `test_currency_wall_census.py` rather than by inspection.

EACH CELL IS PRICED IN THE WORLD ITS SCENARIO DECLARES. `ScenarioCharacter`
carries both `ge_market` (which market) and `unlocked_achievements` (which
access-gated tiles exist), and `plan.py` forwards both per character. A census
that builds one `GameData` and prices 44 cells in it measures a world no
scenario asked for — and for THIS census that is fatal rather than approximate:
every `tasks_coin` sink in the catalogue sells at `tasks_trader`, whose tile is
gated on the `tasks_farmer` achievement, so without the per-cell world the only
funded arm in the set cannot fire and the census reports a clean sweep over an
empty reference set. That failure was measured and shipped once already (see the
wave-6 design §10 retraction); `declared_world` is the fix, and
`REFERENCE_SET_EMPTY` is the alarm that would have caught it.

THE WALL NAMES ARE READ OFF THE CATALOGUE, NOT OFF THE DESIGN. §7 proposed
`WALL_GOLD`, `WALL_EVENT_ONLY` and `WALL_PASSIVE_ACCRUAL`. Measured against the
bundle, two of those three name nothing: gold is not a currency ITEM (it lives
in `state.gold`, so a gold shortfall is charged through the buy route and never
appears as a currency code), and no currency in the catalogue accrues passively.
The names below are the ones the six real currencies actually need, and each is
the negation of one conjunct of `obtain_sources._drop_sources` — live tiles, then
winnability — so the census and production cannot disagree about why a currency
has no route.

`enchanted_coin` and `sonnengott_coin` say in their FLAVOUR TEXT that they are
earned by defeating Pixie and Sonnengott. Both are raid bosses the catalogue
carries with EMPTY drop tables, so no structural fact links coin to boss.
Inferring the link from prose would be inventing data the API did not give, so
both classify on what the catalogue does say — `WALL_NO_PRODUCER` — and the day
the drop tables gain the entry they will reclassify by themselves.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.decisions.root import resolve_root
from artifactsmmo_cli.ai.decisions.route import route_price
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.scenario import (
    SCENARIOS,
    ScenarioCharacter,
    load_bundle_game_data,
    scenario_state,
)
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState

GRANT = 10_000
"""Units of a currency handed to the character for the differential probe.

Large enough to clear any single price in the catalogue (the dearest currency
sink is 245) with room for a whole closure's worth of repeats, so a price that
still does not move is one the currency genuinely does not gate. It is a
DETECTION grant, never a claim the character could get that many."""


class CurrencyGap(Enum):
    """The verdict for one `(scenario, currency)` cell — one not-applicable
    class, one pass class, three named walls, and the residuals."""

    NOT_DEMANDED = "not_demanded"
    """The root's price does not move when this currency is granted, so the
    walk never charged it. The overwhelming majority of cells, and the reason
    the residual's scope has to be printed beside the cell count."""

    ROOT_UNRESOLVED = "root_unresolved"
    """`resolve_root` returned no root for this scenario, so there is no active
    link to price and no cell to judge.

    EXPLAINED, not a residual: O7 asks whether a currency gap ON AN ACTIVE LINK
    is funded or named, and a character the graph sends nowhere has no such
    link. The cell is still emitted — a silently skipped scenario would shrink
    the grid without shrinking the headline claim."""

    FUNDED = "funded"
    """PASS: the walk charged this currency and `is_task_earnable` is true, so a
    funding route exists and `ReachCurrencyGoal` is the node that takes it."""

    WALL_NO_PRODUCER = "wall_no_producer"
    """Charged, and NOTHING in the catalogue produces it: no monster's drop
    table lists the code. An honest end — the bot cannot obtain what the game
    does not model a source for."""

    WALL_EVENT_ONLY = "wall_event_only"
    """Charged, every monster that drops it is EVENT-GATED, and none has a live
    tile right now. The route exists but its content is dormant, which is a
    fact about the world clock rather than about the graph."""

    WALL_UNWINNABLE_DROP = "wall_unwinnable_drop"
    """Charged, at least one dropper is standing on a reachable tile, and this
    character beats none of them at restorable hp. Reachable but unbeatable —
    the answer is gear or levels, and both are roots the graph already has."""

    O7_SILENT_CURRENCY_STALL = "o7_silent_currency_stall"
    """RESIDUAL, and the one the obligation exists for. The walk charged this
    currency at `UNOBTAINABLE_PER_UNIT`, it is not task-earnable, and yet a
    dropper this character CAN beat is standing on a live tile. A route the
    model can see was not priced, so the root is a million actions dear for a
    reason nothing in the graph states."""

    O7_MULTI_CURRENCY_WALL = "o7_multi_currency_wall"
    """RESIDUAL. The root prices as unobtainable, granting every currency at
    once makes it obtainable, and NO single currency does — so two or more
    currencies wall it together and the single-currency probe cannot say which
    owns the gap.

    The gap is real and this census cannot NAME it, which is precisely what O7
    forbids. It is reported rather than passed over because the alternative is
    the shape the obligation exists to prevent: a root priced at a million with
    every cell reading `not_demanded`."""

    O7_UNEXPLAINED = "o7_unexplained"
    """RESIDUAL. Charged, not funded, and not one of the three walls holds —
    the census cannot say why the currency has no route either, which is the
    same failure one layer out."""

    CURRENCY_CATALOGUE_EMPTY = "currency_catalogue_empty"
    """RESIDUAL, and a DATA fault rather than a graph one: the catalogue offers
    no currency rows at all.

    It is a residual and not a wall for the reason O1's `SKILL_CATALOGUE_EMPTY`
    is: without it a bundle that lost its currency rows produces a grid of zero
    cells, every residual is trivially zero, and `--check` exits 0 on a
    corrupted catalogue. `MIN_CELLS` also catches that, and deliberately so —
    the two floors fail for different reasons and neither is the other's
    backstop."""


RESIDUALS = frozenset({CurrencyGap.O7_SILENT_CURRENCY_STALL.value,
                       CurrencyGap.O7_MULTI_CURRENCY_WALL.value,
                       CurrencyGap.O7_UNEXPLAINED.value,
                       CurrencyGap.CURRENCY_CATALOGUE_EMPTY.value})
"""The classes that must reach 0. The three `WALL_*` classes are EXPLAINED,
and `NOT_DEMANDED` / `ROOT_UNRESOLVED` are not judgements at all.

`REFERENCE_SET_EMPTY` is NOT here because it is not a property of any cell —
see `reference_set_residual`."""

MIN_CELLS = 200
"""Blindness floor on the grid, enforced by `gen_currency_wall.py --check` and
not only by the suite.

`--check`'s residual test is satisfied by an EMPTY census — "0 cells, PASS 0"
would print clean and exit 0. `scripts/*` is coverage-omitted and
`census-gate.yml` runs the scripts without pytest, so the floor lives here where
the script and `test_currency_wall_census` read the same number.

200 against a current 264 (44 scenarios x 6 currencies): headroom to retire a
scenario or two without flapping, far too tight for a collapsed sweep."""


@dataclass(frozen=True)
class CurrencyEvidence:
    """Why a currency has no route, decomposed along the exact conjuncts
    `obtain_sources._drop_sources` gates on.

    Every field is a COUNT, a flag or a code list, never a verdict:
    `classify_gap` is the only place a judgement is formed, so the evidence and
    the judgement stay separable in the rendered matrix."""

    #: `game_data.is_task_earnable` — whether completing tasks pays this code.
    task_earnable: bool
    #: Every monster whose drop table lists the code, event-gated or not.
    droppers: tuple[str, ...]
    #: Of those, the ones with a live tile in `all_monster_locations` — the
    #: first conjunct `_drop_sources` gates on. An event monster appears here
    #: only while its event is running.
    on_live_tiles: tuple[str, ...]
    #: Of the live-tiled ones, those `is_winnable` at RESTORABLE hp — the
    #: second conjunct, asked exactly as `_drop_sources` asks it.
    winnable: tuple[str, ...]
    #: Of the droppers, those `game_data.is_event_monster` reports as event
    #: content. Separates a dormant event from a permanent monster with no tile.
    event_gated: tuple[str, ...]


@dataclass(frozen=True)
class CurrencyResult:
    """One cell's answer. Flat and render-ready, like `RungResult`."""

    scenario: str
    currency: str
    root: str
    base_price: int
    granted_price: int
    charged: bool
    evidence: CurrencyEvidence | None
    gap: str

    @property
    def passed(self) -> bool:
        return self.gap in (CurrencyGap.FUNDED.value,
                            CurrencyGap.NOT_DEMANDED.value,
                            CurrencyGap.ROOT_UNRESOLVED.value)


def catalogue_currencies(game_data: GameData) -> tuple[str, ...]:
    """Every code the item catalogue types as a currency, sorted.

    Sorted rather than catalogue-ordered so the matrix is byte-reproducible,
    the same rule `run_census` follows for scenarios."""
    return tuple(sorted(code for code, stats in game_data.items.stats.items()
                        if stats.type_ == "currency"))


def currency_evidence(code: str, state: WorldState,
                      game_data: GameData) -> CurrencyEvidence:
    """The DROP conjuncts for `code`, asked the way `_drop_sources` asks them.

    `replace(state, hp=state.max_hp)` mirrors that function's RESTORABLE-hp
    rule: route existence is not an hp question, and being at 20% hp is a reason
    to Rest rather than a reason to call a monster unbeatable."""
    rested = dataclasses.replace(state, hp=state.max_hp)
    droppers = tuple(monster for monster, _rate, _min_q, _max_q
                     in game_data.monsters_dropping(code))
    on_live_tiles = tuple(
        monster for monster in droppers
        if game_data.all_monster_locations.get(monster))
    winnable = tuple(monster for monster in on_live_tiles
                     if is_winnable(rested, game_data, monster))
    event_gated = tuple(monster for monster in droppers
                        if game_data.is_event_monster(monster))
    return CurrencyEvidence(
        task_earnable=game_data.is_task_earnable(code), droppers=droppers,
        on_live_tiles=on_live_tiles, winnable=winnable,
        event_gated=event_gated)


def classify_gap(charged: bool, evidence: CurrencyEvidence) -> CurrencyGap:
    """The verdict for one charged-or-not currency. Pure, and the ONLY place a
    judgement is formed.

    ORDER IS LOAD-BEARING. The winnable check precedes every wall because a
    beatable dropper on a live tile CONTRADICTS the charge: the model can see
    that route, so a million-action price is a stall and not a wall. Testing
    the walls first would launder that contradiction into
    `wall_unwinnable_drop`, which is the residual quietly renaming itself as an
    explanation."""
    if not charged:
        return CurrencyGap.NOT_DEMANDED
    if evidence.task_earnable:
        return CurrencyGap.FUNDED
    if evidence.winnable:
        return CurrencyGap.O7_SILENT_CURRENCY_STALL
    if not evidence.droppers:
        return CurrencyGap.WALL_NO_PRODUCER
    if evidence.on_live_tiles:
        return CurrencyGap.WALL_UNWINNABLE_DROP
    if len(evidence.event_gated) == len(evidence.droppers):
        return CurrencyGap.WALL_EVENT_ONLY
    return CurrencyGap.O7_UNEXPLAINED


def _granted(state: WorldState, codes: tuple[str, ...]) -> WorldState:
    """`state` with `GRANT` units of each of `codes` added to the bag."""
    inventory = dict(state.inventory)
    for code in codes:
        inventory[code] = inventory.get(code, 0) + GRANT
    return dataclasses.replace(state, inventory=inventory)


def charged_currencies(root: MetaGoal, state: WorldState, game_data: GameData,
                       currencies: tuple[str, ...]) -> dict[str, tuple[int, int]]:
    """`{currency: (base_price, granted_price)}` for every currency the price
    walk charged AT `UNOBTAINABLE_PER_UNIT` while pricing `root`.

    THE DIFFERENTIAL, and the whole of the detector. `route_price` is asked
    twice per currency — once as the character stands, once with `GRANT` units
    in the bag. Nothing here re-derives a closure, so the census cannot drift
    from the pricer the way a second walk would.

    THE TEST IS A CROSSING, NOT A FALL, and the difference is the whole
    precision of the census. Any cheaper route lowers the price: a currency that
    merely buys a material for fewer actions than gathering it would make
    `price < base` true while nothing was ever charged as unobtainable, and the
    cell would classify as a WALL on a currency that walls nothing. So a charge
    requires the root to be UNOBTAINABLE as the character stands
    (`base >= UNOBTAINABLE_PER_UNIT`) and OBTAINABLE once the currency is held
    (`price < UNOBTAINABLE_PER_UNIT`) — the currency's absence is then precisely
    what made the root unpriceable. The witnessed case reads 1_000_001 -> 5.

    WHAT A SINGLE-CURRENCY PROBE CANNOT SEE: a root walled on TWO currencies
    stays above the threshold when either one alone is granted, so neither would
    be attributed and the gap would go unnamed — which is the silent stall this
    obligation exists to forbid. `run_census` therefore asks one further
    question per scenario, granting every currency at once; a root that crosses
    only then is a real gap this probe cannot attribute, and is reported as
    `O7_MULTI_CURRENCY_WALL` rather than passed over."""
    base = route_price(root, state, game_data, NO_PROFILE_CONTEXT, None)
    out: dict[str, tuple[int, int]] = {}
    if base < UNOBTAINABLE_PER_UNIT:
        return out
    for code in currencies:
        price = route_price(root, _granted(state, (code,)), game_data,
                            NO_PROFILE_CONTEXT, None)
        if price < UNOBTAINABLE_PER_UNIT:
            out[code] = (base, price)
    return out


def unattributed_wall(root: MetaGoal, state: WorldState, game_data: GameData,
                      currencies: tuple[str, ...]) -> bool:
    """Is `root` unobtainable for a CURRENCY reason no single currency explains?

    True when the root prices as unobtainable, no one currency crosses the
    threshold on its own, and granting them ALL does. The only shapes that
    produce it are a root walled on two or more currencies at once — so the gap
    is real, this probe cannot say which code owns it, and O7's promise that
    every currency gap is funded or NAMED is not met. That is a residual, not a
    pass.

    A root walled on a non-currency leaf — the ordinary case, and most of the
    grid — is unaffected: granting every currency leaves it exactly as
    unobtainable as it was."""
    base = route_price(root, state, game_data, NO_PROFILE_CONTEXT, None)
    if base < UNOBTAINABLE_PER_UNIT:
        return False
    everything = route_price(root, _granted(state, currencies), game_data,
                             NO_PROFILE_CONTEXT, None)
    return everything < UNOBTAINABLE_PER_UNIT


def declared_world(scenario: ScenarioCharacter, bundle: Path,
                   cache: dict[tuple[bool, tuple[str, ...]], GameData]
                   ) -> GameData:
    """The `GameData` THIS scenario declares, memoised on its declaration.

    Both fields matter and both are read off the scenario rather than chosen
    here — see the module docstring for what forcing a single world costs this
    particular census."""
    key = (scenario.ge_market, tuple(scenario.unlocked_achievements))
    if key not in cache:
        cache[key] = load_bundle_game_data(
            bundle, with_ge_orders=key[0],
            completed_achievements=frozenset(key[1]))
    return cache[key]


def run_census(bundle: Path) -> list[CurrencyResult]:
    """Every `(scenario, currency)` cell, in scenario-declaration order then
    sorted currency order — both fixed vocabularies, so the matrix is
    byte-reproducible.

    Takes the BUNDLE PATH rather than a `GameData`, unlike its sibling censuses,
    because the world is a per-scenario fact here and a single-`GameData`
    signature is exactly the mistake that voided this census's first run."""
    cache: dict[tuple[bool, tuple[str, ...]], GameData] = {}
    results: list[CurrencyResult] = []
    for name, scenario in SCENARIOS.items():
        game_data = declared_world(scenario, bundle, cache)
        currencies = catalogue_currencies(game_data)
        if not currencies:
            results.append(CurrencyResult(
                scenario=name, currency="-", root="-", base_price=0,
                granted_price=0, charged=False, evidence=None,
                gap=CurrencyGap.CURRENCY_CATALOGUE_EMPTY.value))
            continue
        state = scenario_state(scenario, game_data)
        root = resolve_root(state, game_data,
                            CharacterObjective.from_game_data(game_data),
                            NO_PROFILE_CONTEXT, None).root
        if root is None:
            results.extend(
                CurrencyResult(
                    scenario=name, currency=code, root="-", base_price=0,
                    granted_price=0, charged=False, evidence=None,
                    gap=CurrencyGap.ROOT_UNRESOLVED.value)
                for code in currencies)
            continue
        charges = charged_currencies(root, state, game_data, currencies)
        # Only worth asking when NOTHING was attributed: if some currency already
        # crossed on its own, the gap has a name and the combined probe would
        # merely re-confirm it at the cost of another price walk.
        unattributed = (not charges
                        and unattributed_wall(root, state, game_data,
                                              currencies))
        for code in currencies:
            evidence = currency_evidence(code, state, game_data)
            base, granted = charges.get(code, (0, 0))
            gap = (CurrencyGap.O7_MULTI_CURRENCY_WALL if unattributed
                   else classify_gap(code in charges, evidence))
            results.append(CurrencyResult(
                scenario=name, currency=code, root=repr(root),
                base_price=base, granted_price=granted,
                charged=code in charges, evidence=evidence, gap=gap.value))
    return results


def reference_set_residual(results: list[CurrencyResult]) -> str | None:
    """`REFERENCE_SET_EMPTY`, the residual that is a property of the GRID and
    not of any cell — so it lives here rather than in `CurrencyGap`.

    O7's own text: *"fail if the funded arm is exercised zero times"*. Every
    wall class could be correct, every residual zero, and the census still be
    worthless if nothing ever reached the arm the obligation is about. This is
    the alarm that fires when the funded arm has no witness — the exact state
    the census's first run was in, undetected, because it priced 44 cells in a
    world whose only `tasks_coin` vendor had no tile."""
    funded = sum(1 for r in results if r.gap == CurrencyGap.FUNDED.value)
    if funded:
        return None
    return ("reference_set_empty: the FUNDED arm was exercised 0 times, so "
            "every residual below is trivially zero and this census proves "
            "nothing. O7 requires at least one cell whose charged currency is "
            "task-earnable.")


def summary_line(results: list[CurrencyResult]) -> str:
    """One-line completeness metric: cells, distinct currencies, the arm
    counts, and every must-be-zero residual — including
    `currency_catalogue_empty`, so a bundle that lost its currency rows is
    visible in the headline and not only in the `--check` failure list."""
    def count(gap: CurrencyGap) -> int:
        return sum(1 for r in results if r.gap == gap.value)

    walls = sum(1 for r in results if r.gap.startswith("wall_"))
    currencies = {r.currency for r in results}
    return (f"{len(results)} cells over {len(currencies)} currencies; "
            f"charged {sum(1 for r in results if r.charged)}; "
            f"FUNDED {count(CurrencyGap.FUNDED)}; walled {walls}; "
            f"not_demanded {count(CurrencyGap.NOT_DEMANDED)}; "
            f"root_unresolved {count(CurrencyGap.ROOT_UNRESOLVED)}; "
            f"o7_silent_currency_stall "
            f"{count(CurrencyGap.O7_SILENT_CURRENCY_STALL)}; "
            f"o7_multi_currency_wall "
            f"{count(CurrencyGap.O7_MULTI_CURRENCY_WALL)}; "
            f"o7_unexplained {count(CurrencyGap.O7_UNEXPLAINED)}; "
            f"currency_catalogue_empty "
            f"{count(CurrencyGap.CURRENCY_CATALOGUE_EMPTY)}")


def demand_breakdown(results: list[CurrencyResult]) -> str:
    """Which currencies the price walk actually charges, and how many cells
    each.

    THE RESIDUAL'S SCOPE, STATED OUT LOUD, in the shape of O1's
    `routing_breakdown`. Every residual class requires `charged`, so a currency
    no root ever demands can only ever be `not_demanded` — never a wall, never a
    residual. A "0 residuals" headline over 264 cells therefore promises far
    less than the cell count implies, and this line is what stops that headline
    being read as a sweep. Computed rather than transcribed, so a scenario that
    widens the charged set updates it by itself."""
    counts: dict[str, int] = {}
    for result in results:
        if result.charged:
            counts[result.currency] = counts.get(result.currency, 0) + 1
    charged = sum(counts.values())
    listed = ", ".join(
        f"{code} {counts[code]}"
        for code in sorted(counts, key=lambda name: (-counts[name], name)))
    return (f"residual scope: {charged} of {len(results)} cells are CHARGED "
            f"({len(counts)} distinct currencies) — {listed or 'none'}. "
            f"An uncharged currency can only be not_demanded.")


def render_matrix(results: list[CurrencyResult]) -> str:
    """The cell x verdict matrix. Pure markdown — the generator script owns the
    file write."""
    empty = reference_set_residual(results)
    lines = [
        "# O7 Currency-Wall Census — Matrix",
        "",
        "> GENERATED — do not hand-edit. Regenerate with "
        "`uv run python scripts/gen_currency_wall.py`.",
        ">",
        "> Obligation O7 (wave-6 routes design §7): every currency the price "
        "walk charged at `UNOBTAINABLE_PER_UNIT` while pricing a scenario's "
        "resolved root is either task-earnable (FUNDED) or falls into a named "
        "wall. The residual is a charged currency with a BEATABLE dropper on a "
        "live tile — a route the model can see that the price did not take.",
        ">",
        "> `charged` is a differential on production's own pricer: the root is "
        "priced as the character stands and again with the currency granted, "
        "and a fall in price is the charge. No closure is re-derived here — "
        "obligation O6 forbids a second cost model, and this census must not "
        "be one.",
        ">",
        "> Every field `classify_gap` reads is a column: `droppers`, "
        "`live tiles` and `winnable` are the two conjuncts "
        "`obtain_sources._drop_sources` gates on, and `event` separates a "
        "dormant event from a permanent monster with no tile.",
        "",
        summary_line(results),
        "",
        demand_breakdown(results),
        "",
    ]
    if empty:
        lines.extend([f"**{empty}**", ""])
    lines.extend([
        "| Scenario | Currency | Verdict | charged | base | granted | "
        "earnable | droppers | live tiles | winnable | event |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ])
    for result in results:
        verdict = "PASS" if result.passed else f"**{result.gap}**"
        evidence = result.evidence
        if evidence is None:
            lines.append(
                f"| {result.scenario} | {result.currency} | {verdict} | - "
                f"| - | - | - | - | - | - | - |")
            continue
        lines.append(
            f"| {result.scenario} | {result.currency} | {verdict} "
            f"| {'yes' if result.charged else '-'} "
            f"| {result.base_price} | {result.granted_price} "
            f"| {'yes' if evidence.task_earnable else '-'} "
            f"| {len(evidence.droppers)} | {len(evidence.on_live_tiles)} "
            f"| {len(evidence.winnable)} | {len(evidence.event_gated)} |")
    lines.append("")
    return "\n".join(lines) + "\n"

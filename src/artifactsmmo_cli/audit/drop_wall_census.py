"""The unwinnable-dropper wall, measured where it actually binds: the CANDIDATES.

`obtain_sources._drop_sources` withholds a DROP route when the dropper is not
`is_winnable` at restorable hp. The item then has no drop route; if it has no
other, the pricer charges `UNOBTAINABLE_PER_UNIT` and every recipe consuming it
inherits infinity. Nothing in the model says *"you cannot beat the thing that
drops this"* — the 2026-08-09 exclusion audit ranked this the biggest unfixed
wall of its twenty sites.

WHY EVERY EARLIER CENSUS WAS BLIND TO IT, AND WHY THIS ONE IS NOT. Every census
in this repo prices the RESOLVED root — the argmax of the tier walk. Measured
that way the wall names nothing: 42 roots resolved, 27 priced unobtainable, 4
walled on an ingredient, and **0** of those on an unwinnable dropper. That
reading is wrong, and instructively so. **An infinite price is a veto.** A
candidate walled at infinity never becomes the argmax, so a differential that
only asks about the winner cannot see what the wall is doing. Priced over root +
every alternative — `RootResolution.alternatives`, the set `_servable_promotion`
walks — 448 candidates, 371 unobtainable, **9 crossing**. Same shape as the gold
row's blindness one layer up: the name was fine, the grid could not see its
subject.

DETECTION IS A CROSSING DIFFERENTIAL, NOT A SECOND CLOSURE WALK. The pricer does
not report what it walled on, and re-deriving the demand closure here would be
the second cost model obligation O6 forbids — the drift it forbids it for. So
the census asks production's own pricer twice: price the candidate as it stands,
then price it again with the unwinnable-dropper items granted into the bag. A
price that FALLS was paying an unobtainable charge for one of them. One pricer,
no rival walk, and the detector is pinned by positive controls in
`test_drop_wall_census.py` rather than by inspection.

THE GRANT SET IS THE NEGATION OF `_drop_sources`' OWN CONJUNCTS — some monster
drops the item, at least one dropper stands on a tile in `all_monster_locations`,
and none of those is `is_winnable` at restorable hp. Reading the same three facts
production reads is what keeps the census and the pricer from disagreeing about
why a route is absent, exactly as the currency census reads them for its own
walls.

EACH CELL IS PRICED IN THE WORLD ITS SCENARIO DECLARES. `ScenarioCharacter`
carries `ge_market` and `unlocked_achievements` and `plan.py` forwards both, so a
census that builds ONE `GameData` measures a world no scenario asked for. That
failure has been shipped once already (wave-6 design §10 retraction);
`declared_world` is the fix here as it is there.

THE TWO NAMES ARE SPLIT BY `combat_deficit`, WHICH IS WHAT MADE THIS CENSUS
POSSIBLE. In 2026-08-09 this wall stayed unfixed because *"cost to become able to
beat monster X has no simple measure and is circular"*. `combat_deficit` now
returns a gear chain and a `closes` verdict, so the census can say which walls a
future `_gated_drop_option` could price and which are terminal.

THE CENSUS MEASURES THE STRUCTURAL WALL, NOT WHAT PRODUCTION CURRENTLY CHARGES,
and that distinction became load-bearing the day `_gated_drop_option` shipped.
Every price here is taken with `gated_drop=False` — the routes `obtain_sources`
serves today — so a wall stays COUNTED after the pricer learns to open it. The
`gate_price` column then says which of those walls the gate does open. Measuring
only the gated price makes the census's own subject vanish as the fix lands: it
did exactly that on contact, dropping 9 walls to 7 and reporting the fix as a
broken census. A census that stops seeing its subject when the subject is being
handled is not a census, it is a thermometer that melts.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.combat_deficit import combat_deficit
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
"""Units of a walled item handed to the character for the differential probe.

Large enough that no recipe multiplicity in the catalogue can keep the demand
open — the dearest drop demand in the committed set is 6 — so a price that still
does not move is one the item genuinely does not gate. A DETECTION grant, never
a claim the character could get that many."""

MIN_CELLS = 300
"""Blindness floor on the grid, enforced by `gen_drop_wall.py --check` and not
only by the suite.

`--check`'s residual test is satisfied by an EMPTY census: "0 cells, 0
residuals" would print clean and exit 0, the flattering-gate failure this repo
has shipped once already. `scripts/*` is coverage-omitted and the census gate
runs the scripts without pytest, so the floor lives here where the script and
the suite read the same number.

300 against a current 448 (root + alternatives over 44 scenarios): headroom to
retire a scenario without flapping, far too tight for a collapsed sweep."""


class DropGap(Enum):
    """One verdict per `(scenario, candidate root)` cell."""

    OBTAINABLE = "obtainable"
    """The candidate prices below `UNOBTAINABLE_PER_UNIT`. Not a wall, and not a
    judgement — most of the grid."""

    NOT_DROP_WALLED = "not_drop_walled"
    """Priced unobtainable, and granting every unwinnable-dropper item leaves it
    exactly as unobtainable. The wall is real but it is somebody else's — a gold
    price, a skill gate, an item with no producer at all. This census says so
    rather than staying silent, because a cell it cannot classify and a cell that
    is not its subject must not read the same."""

    WALL_DROPPER_UNWINNABLE_CLOSES = "wall_dropper_unwinnable_closes"
    """Priced unobtainable, crosses when the item is granted, every live dropper
    is unbeatable at restorable hp, and `combat_deficit` CLOSES the margin with a
    gear chain.

    The chicken-and-egg the 2026-08-09 audit named: you need the gear to beat the
    mob that drops the material for the gear. This is the priceable arm — the one
    a `_gated_drop_option` would open, mirroring `_gated_craft_option` — and
    naming it is what turns "the pricer says a million" into a statement the
    model makes on purpose."""

    WALL_DROPPER_OUT_OF_REACH = "wall_dropper_out_of_reach"
    """As above, but `combat_deficit` does NOT close: no chain in the catalogue
    lifts the margin over this monster. An honest terminal wall, and the arm a
    future pricing change must decline rather than charge."""

    DROP_WALL_UNATTRIBUTED = "drop_wall_unattributed"
    """RESIDUAL. The candidate crosses when the walled items are granted TOGETHER
    and no single one of them crosses on its own, so two or more drop walls hold
    it up at once and this probe cannot say which owns the gap.

    The gap is real and unnamed, which is the state the census exists to
    prevent. Reported rather than passed over, exactly as the currency census
    reports `o7_multi_currency_wall`."""

    ROOT_UNRESOLVED = "root_unresolved"
    """The tier walk returned no root for this scenario, so there is no
    candidate to price. 2 of the 44 committed scenarios sit here.

    NOT a residual, on the same reading its currency sibling takes: a walk that
    offers nothing is a fact about that scenario, not a failure of this census,
    and failing the gate on it would make this census the enforcer of a property
    it does not measure. The class exists so such a scenario contributes a VISIBLE
    row instead of silently contributing zero cells — `MIN_CELLS` and
    `witness_residual` are what cover the blind-sweep case."""


RESIDUALS = frozenset({DropGap.DROP_WALL_UNATTRIBUTED.value})
"""The class that must reach 0. Both `WALL_*` classes are EXPLAINED — the
catalogue, not the graph, is why the route is absent — and `OBTAINABLE`,
`NOT_DROP_WALLED` and `ROOT_UNRESOLVED` are not judgements about this census's
subject at all."""


@dataclass(frozen=True)
class DropEvidence:
    """Why an item has no drop route, decomposed along the exact conjuncts
    `obtain_sources._drop_sources` gates on.

    Carried per cell so the matrix can show WHY a verdict landed without the
    reader re-deriving it, and so a wall arm that stops being reachable is
    visible as a column of zeros rather than as an absent row."""

    item: str
    droppers: tuple[str, ...]
    on_live_tiles: tuple[str, ...]
    closes: tuple[str, ...]
    """Live droppers whose margin `combat_deficit` closes with a gear chain."""
    chain: tuple[str, ...]
    """The chain for the first closing dropper — the acquisitions that would
    open this route. Empty when nothing closes."""


@dataclass(frozen=True)
class DropResult:
    """One `(scenario, candidate root)` cell."""

    scenario: str
    candidate: str
    is_resolved_root: bool
    """True for the argmax, False for an alternative. The column that makes §2's
    finding legible: every wall in the committed set sits on an alternative, so a
    matrix that could not tell them apart would read as a contradiction of every
    earlier census rather than as the completion of one."""

    base_price: int
    granted_price: int
    gate_price: int
    """The same candidate priced WITH `_gated_drop_option` — the "beat the
    monster once you own the gear" route.

    THE CENSUS MEASURES THE STRUCTURAL WALL AND THE FIX SEPARATELY, and it has
    to. `base_price` is taken with the gate OFF, so a wall stays counted after
    production starts pricing it; this column says which of those walls the gate
    now opens. Measuring only the gated price makes the census's own subject
    disappear as the fix lands — its witness floor fired on exactly that the day
    the gate shipped, reporting success as a broken census.

    STORE-LESS, like everything else here: the census has no `learning.db`, and
    every one of these unlocks is gear whose craft is skill-gated, so the gate
    opens fewer cells here than it does live with an observed grind rate. Both
    numbers are honest about different worlds; this one is reproducible."""

    gap: str
    evidence: DropEvidence | None

    @property
    def passed(self) -> bool:
        return self.gap not in RESIDUALS


def declared_world(scenario: ScenarioCharacter, bundle: Path,
                   cache: dict[tuple[bool, tuple[str, ...]], GameData]
                   ) -> GameData:
    """The `GameData` THIS scenario declares, memoised on its declaration.

    Both fields are read off the scenario rather than chosen here — see the
    module docstring for what forcing a single world costs a census like this
    one."""
    key = (scenario.ge_market, tuple(scenario.unlocked_achievements))
    if key not in cache:
        cache[key] = load_bundle_game_data(
            bundle, with_ge_orders=key[0],
            completed_achievements=frozenset(key[1]))
    return cache[key]


def unwinnable_drop_items(state: WorldState, game_data: GameData) -> tuple[str, ...]:
    """Items whose ONLY drop route `_drop_sources` withholds on winnability.

    The three conjuncts, in the order that source reads them: some monster drops
    it, at least one of those stands on a tile `factory.py` builds a `FightAction`
    from, and none of those is winnable at RESTORABLE hp.

    Restorable, not current: route EXISTENCE is not an hp question. Being at 20%
    hp is a reason to Rest — an action the planner has — while a fight the
    character cannot win when full is a route that does not exist. This is the
    same reading `_drop_sources` takes, and taking a different one here would
    make the census disagree with the pricer about its own subject."""
    rested = replace(state, hp=state.max_hp)
    walled: list[str] = []
    for item in game_data.items.stats:
        live = [monster for monster, _rate, _min_q, _max_q
                in game_data.monsters_dropping(item)
                if game_data.all_monster_locations.get(monster)]
        if not live:
            continue
        if any(is_winnable(rested, game_data, monster) for monster in live):
            continue
        walled.append(item)
    return tuple(walled)


def _granted(state: WorldState, items: tuple[str, ...]) -> WorldState:
    """`state` with `GRANT` of each item added to the bag."""
    inventory = dict(state.inventory)
    for item in items:
        inventory[item] = inventory.get(item, 0) + GRANT
    return replace(state, inventory=inventory)


def drop_evidence(item: str, state: WorldState, game_data: GameData) -> DropEvidence:
    """The three conjuncts plus `combat_deficit`'s verdict, for one item.

    `combat_deficit` is asked at restorable hp for the same reason
    `unwinnable_drop_items` is: it answers "what gear closes this fight", which is
    not a question about the character's current hp."""
    rested = replace(state, hp=state.max_hp)
    droppers = tuple(monster for monster, _rate, _min_q, _max_q
                     in game_data.monsters_dropping(item))
    live = tuple(monster for monster in droppers
                 if game_data.all_monster_locations.get(monster))
    closes: list[str] = []
    chain: tuple[str, ...] = ()
    for monster in live:
        deficit = combat_deficit(rested, game_data, monster)
        if deficit is not None and deficit.closes:
            closes.append(monster)
            if not chain:
                chain = tuple(step.code for step in deficit.chain)
    return DropEvidence(item=item, droppers=droppers, on_live_tiles=live,
                        closes=tuple(closes), chain=chain)


def classify(candidate: MetaGoal, state: WorldState, game_data: GameData,
             walled: tuple[str, ...]
             ) -> tuple[str, int, int, int, DropEvidence | None]:
    """`(gap, base_price, granted_price, evidence)` for one candidate.

    THE ORDER OF THE TWO PROBES IS LOAD-BEARING. The collective grant is asked
    FIRST and the per-item attribution only on a candidate that crossed: pricing
    every walled item individually against every unobtainable candidate is 371 x
    68 walks for an answer that is `NOT_DROP_WALLED` in all but nine of them.
    Asking the cheap question first is also what makes `DROP_WALL_UNATTRIBUTED`
    expressible — it is precisely "the collective probe crossed and no single one
    did", which a per-item-only sweep could not distinguish from a clean pass."""
    base = route_price(candidate, state, game_data, NO_PROFILE_CONTEXT, None,
                       gated_drop=False)
    if base < UNOBTAINABLE_PER_UNIT:
        return (DropGap.OBTAINABLE.value, base, base, base, None)
    if not walled:
        return (DropGap.NOT_DROP_WALLED.value, base, base, base, None)
    collective = route_price(candidate, _granted(state, walled), game_data,
                             NO_PROFILE_CONTEXT, None, gated_drop=False)
    if collective >= base:
        return (DropGap.NOT_DROP_WALLED.value, base, collective, base, None)
    gate_price = route_price(candidate, state, game_data, NO_PROFILE_CONTEXT,
                             None, gated_drop=True)
    for item in walled:
        single = route_price(candidate, _granted(state, (item,)), game_data,
                             NO_PROFILE_CONTEXT, None, gated_drop=False)
        if single >= base:
            continue
        evidence = drop_evidence(item, state, game_data)
        gap = (DropGap.WALL_DROPPER_UNWINNABLE_CLOSES if evidence.closes
               else DropGap.WALL_DROPPER_OUT_OF_REACH)
        return (gap.value, base, single, gate_price, evidence)
    return (DropGap.DROP_WALL_UNATTRIBUTED.value, base, collective, gate_price,
            None)


def run_census(bundle: Path) -> list[DropResult]:
    """Every `(scenario, candidate root)` cell, in scenario-declaration order
    then walk order — both fixed, so the matrix is byte-reproducible.

    Takes the BUNDLE PATH rather than a `GameData`, like its currency sibling and
    unlike the older censuses: the world is a per-scenario fact here, and a
    single-`GameData` signature is the mistake that voided the first run of the
    census this one is modelled on."""
    cache: dict[tuple[bool, tuple[str, ...]], GameData] = {}
    results: list[DropResult] = []
    for name, scenario in SCENARIOS.items():
        game_data = declared_world(scenario, bundle, cache)
        state = scenario_state(scenario, game_data)
        resolution = resolve_root(state, game_data,
                                  CharacterObjective.from_game_data(game_data),
                                  NO_PROFILE_CONTEXT, None)
        if resolution.root is None:
            results.append(DropResult(
                scenario=name, candidate="-", is_resolved_root=True,
                base_price=0, granted_price=0, gate_price=0,
                gap=DropGap.ROOT_UNRESOLVED.value, evidence=None))
            continue
        walled = unwinnable_drop_items(state, game_data)
        candidates = (resolution.root, *resolution.alternatives)
        for index, candidate in enumerate(candidates):
            gap, base, granted, gate_price, evidence = classify(
                candidate, state, game_data, walled)
            results.append(DropResult(
                scenario=name, candidate=repr(candidate),
                is_resolved_root=index == 0, base_price=base,
                granted_price=granted, gate_price=gate_price, gap=gap,
                evidence=evidence))
    return results


def witness_residual(results: list[DropResult]) -> str | None:
    """The residual that is a property of the GRID rather than of any cell.

    Every wall class could be correct, every cell residual zero, and the census
    still be worthless if the arm it exists to measure has no witness — the exact
    state the currency census's first run was in, undetected, for a whole
    section. This is the alarm for that, and it is why the census is worth
    running at all rather than a note in a design doc."""
    if any(r.gap == DropGap.WALL_DROPPER_UNWINNABLE_CLOSES.value
           or r.gap == DropGap.WALL_DROPPER_OUT_OF_REACH.value
           for r in results):
        return None
    return ("drop_wall_unwitnessed: no cell reached either wall arm, so every "
            "residual below is trivially zero and this census proves nothing. "
            "The committed bundle exercised the CLOSES arm 9 times when this "
            "census was written; a zero here means the fixture set, the "
            "pricer or the detector moved.")


def summary_line(results: list[DropResult]) -> str:
    """One-line completeness metric: cells, the arm counts, and every
    must-be-zero residual."""
    def count(gap: DropGap) -> int:
        return sum(1 for r in results if r.gap == gap.value)

    walls = sum(1 for r in results if r.gap.startswith("wall_"))
    on_alternatives = sum(1 for r in results
                          if r.gap.startswith("wall_") and not r.is_resolved_root)
    opened = sum(1 for r in results if r.gap.startswith("wall_")
                 and r.gate_price < UNOBTAINABLE_PER_UNIT)
    return (f"{len(results)} candidate cells over {len(SCENARIOS)} scenarios; "
            f"gate opens {opened} of {walls} walls (store-less); "
            f"obtainable {count(DropGap.OBTAINABLE)}; "
            f"not_drop_walled {count(DropGap.NOT_DROP_WALLED)}; "
            f"walled {walls} ({on_alternatives} on ALTERNATIVES); "
            f"closes {count(DropGap.WALL_DROPPER_UNWINNABLE_CLOSES)}; "
            f"out_of_reach {count(DropGap.WALL_DROPPER_OUT_OF_REACH)}; "
            f"drop_wall_unattributed {count(DropGap.DROP_WALL_UNATTRIBUTED)}; "
            f"root_unresolved {count(DropGap.ROOT_UNRESOLVED)}")


def argmax_blindness(results: list[DropResult]) -> str:
    """How many walls a resolved-root-only census would have seen — computed, not
    transcribed, so the claim cannot rot into a comment about a fixture set that
    has since moved.

    This line IS §2 of the design. A reader who takes "0 walls on the resolved
    root" as "no wall" is making exactly the inference the veto invalidates."""
    walls = [r for r in results if r.gap.startswith("wall_")]
    on_root = sum(1 for r in walls if r.is_resolved_root)
    return (f"argmax blindness: {on_root} of {len(walls)} walls sit on a "
            f"RESOLVED root. A census that prices only the argmax sees those "
            f"{on_root} and misses {len(walls) - on_root} — an infinite price is "
            f"a veto, so a walled candidate never becomes the argmax.")


def render_matrix(results: list[DropResult]) -> str:
    """The cell x verdict matrix. Pure markdown — the generator script owns the
    file write."""
    unwitnessed = witness_residual(results)
    lines = [
        "# Drop-Wall Census — Matrix",
        "",
        "> GENERATED — do not hand-edit. Regenerate with "
        "`uv run python scripts/gen_drop_wall.py`.",
        ">",
        "> Every candidate root the tier walk offers — the argmax AND its "
        "alternatives — that prices at `UNOBTAINABLE_PER_UNIT` is either not "
        "this census's subject (`not_drop_walled`) or falls into a named "
        "unwinnable-dropper wall. The residual is a candidate that crosses on "
        "the collective grant with no single item owning the gap.",
        ">",
        "> ALTERNATIVES, not just the winner: an infinite price is a veto, so a "
        "drop-walled candidate never becomes the argmax and a census that "
        "prices only the resolved root cannot see this wall at all.",
        ">",
        "> The crossing is a differential on production's own pricer — the "
        "candidate priced as it stands, then again with the walled items "
        "granted. No closure is re-derived here; obligation O6 forbids a second "
        "cost model and this census must not be one.",
        "",
        summary_line(results),
        "",
        argmax_blindness(results),
        "",
    ]
    if unwitnessed:
        lines.extend([f"**{unwitnessed}**", ""])
    lines.extend([
        "| Scenario | Candidate | Root? | Verdict | base | granted | gated "
        "| item | droppers | live tiles | closes | chain |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ])
    for result in results:
        verdict = "PASS" if result.passed else f"**{result.gap}**"
        root_col = "argmax" if result.is_resolved_root else "alt"
        evidence = result.evidence
        if evidence is None:
            lines.append(
                f"| {result.scenario} | {result.candidate} | {root_col} "
                f"| {verdict} | {result.base_price} | {result.granted_price} "
                f"| {result.gate_price} | - | - | - | - | - |")
            continue
        lines.append(
            f"| {result.scenario} | {result.candidate} | {root_col} "
            f"| {verdict} | {result.base_price} | {result.granted_price} "
            f"| {result.gate_price} | {evidence.item} | {len(evidence.droppers)} "
            f"| {len(evidence.on_live_tiles)} | {len(evidence.closes)} "
            f"| {', '.join(evidence.chain) or '-'} |")
    lines.append("")
    return "\n".join(lines) + "\n"

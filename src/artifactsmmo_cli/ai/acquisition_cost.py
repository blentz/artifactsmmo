"""Hoist priced `RouteOption`s out of `obtain_sources` for the pure cost walk.

The impure half of the route-aware acquisition cost: this module reads
`GameData` and `WorldState`, `ai/acquisition_cost_core` does the arithmetic.

WHY THE ROUTES COME FROM `obtain_sources` AND NOWHERE ELSE. That module was
written to be *"THE model of how an item can be obtained — the one source of
truth every producer of a plan must consume"*, and it enumerates all six routes
with their yields and capacities. Until now no COST model consumed it: `J`
priced through `min_plan_length` (gather/craft/equip, blind to the other three)
and `bid_vs_craft` priced through its own seconds-denominated walk (which knows
drop farms but not vendors). Two models, disjoint coverage, incomparable units,
and the enumeration they should both have been reading sat unused. This module
is the connection, so a SEVENTH route becomes one edit to `obtain_sources` and
every consumer — including the price — gains it structurally.

The one thing added here that `Source` does not carry is the VENUE and the
per-application ACTION COUNT, because those are pricing concerns and `Source`
answers an availability question. Everything else — which routes exist, their
yields, their capacities, whether the executor can actually serve them — is
`obtain_sources`' answer, unmodified. Restating any of it here would recreate
the divergence the epic exists to remove.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timezone
from fractions import Fraction
from math import ceil

from artifactsmmo_cli.ai.acquisition_cost_core import (
    BANK_VENUE,
    UNOBTAINABLE_PER_UNIT,
    RouteOption,
    bundle_acquisition_cost,
    priced_route,
    route_legs,
)
from artifactsmmo_cli.ai.attempt_prospecting import fight_prospecting, gather_prospecting
from artifactsmmo_cli.ai.combat import MIN_WIN_SAMPLES
from artifactsmmo_cli.ai.combat_deficit import combat_deficit
from artifactsmmo_cli.ai.drop_leg import DropLeg
from artifactsmmo_cli.ai.event_availability import event_npc_tradeable
from artifactsmmo_cli.ai.expected_damage import expected_damage_per_fight
from artifactsmmo_cli.ai.fight_seconds_core import FightSecondsModel
from artifactsmmo_cli.ai.fight_walk import walk_seconds
from artifactsmmo_cli.ai.fleet_climb_core import amortized_climb_seconds
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.fight_loop_cost import cycles_per_kill, loss_cost
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loss_risk_core import loss_surcharge
from artifactsmmo_cli.ai.obtain_model.gate import GateKind
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import LEGACY, Policy
from artifactsmmo_cli.ai.obtain_model.route import Route
from artifactsmmo_cli.ai.obtain_sources import (
    UNBOUNDED_CAPACITY,
    Source,
    SourceKind,
    obtain_sources,
)
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.skill_credit import credit_demanded_skills
from artifactsmmo_cli.ai.skill_grind_cost_core import skill_grind_cycles
from artifactsmmo_cli.ai.world_state import GOLD_CODE, WorldState

EQUIP_ACTIONS = 1
"""One `EquipAction`. Carries no venue: equipping happens wherever the character
is standing."""


def _workshop_venue(skill: str) -> str:
    """Workshop tiles are keyed by SKILL, so two crafts on the same skill pay one
    hop and a jewelry craft after a weapon craft pays two. Prefixed so a skill
    named like an NPC cannot collide with one."""
    return f"workshop:{skill}"


def _loss_surcharge(monster_code: str, max_hp: int,
                    records: Sequence[tuple[str, int, int]], fight_seconds: Fraction) -> Fraction:
    """Fight-equivalents the learned losses add to one win against
    `monster_code` (`loss_risk_core`, proved in `Formal.LossRisk`). USER
    2026-10-08, "Price the loss risk": expected fights per win is `1/p`, and
    each loss is charged its death plus recovery (`fight_loop_cost.loss_cost`).
    A monster absent from `records` has never been lost to here: no surcharge.

    Live R2D2 2026-10-08 fought king_slime 22 times at L30 for 14 wins (64%)
    for its jewelrycrafting rung's `king_slimeball`; the veto (< 40%) never
    fired, and the rung was priced as if every fight were a win.

    Exact, as `loss_surcharge` proves it (ruling T3e m1): the win's cost is a
    `Fraction` from its source, so the once-per-route ceiling rounds the true
    value."""
    cost = loss_cost(max_hp, fight_seconds)
    for monster, samples, wins in records:
        if monster == monster_code:
            return loss_surcharge(samples, wins, MIN_WIN_SAMPLES,
                                  cost.numerator, cost.denominator)
    return Fraction(0)


def leg_prospecting(leg: DropLeg, state: WorldState, game_data: GameData) -> int:
    """The prospecting the loadout `leg` is attempted in carries: the fight's
    for a farm leg, the gather's for a gather leg (`attempt_prospecting`)."""
    if leg.kind is SourceKind.DROP:
        return fight_prospecting(leg.source, state, game_data)
    return gather_prospecting(leg.source, state, game_data)


def _drop_actions(item: str, monster_code: str, rate: int, min_q: int, max_q: int,
                  state: WorldState, game_data: GameData, timing: FightSecondsModel,
                  evidence: LearnedDrops,
                  records: Sequence[tuple[str, int, int]] = ()) -> Fraction:
    """Whole-loop actions to farm ONE unit off `monster_code`, exact.

    Two pieces, multiplied, and neither is restated here: the wins one unit
    takes (`LearnedDrops.attempts_per_unit`, the learned chance proved in
    `Formal.DropChance`, at the fight loadout's prospecting,
    `fight_prospecting`) times `cycles_per_kill` — the SAME
    fight-plus-forced-rest figure `cheapest_path_to_level` spends, so a drop farm
    and a level grind are quoted in identical units. Using a bare kill count here
    would price the farm at roughly half its real cost, which is the defect
    `fight_loop_cost` was written to fix.

    Each kill also carries the learned loss surcharge (`_loss_surcharge`): a
    kill is a WIN, and the losses expected per win are paid with it.

    Exact, as a gather and a fight for gold are (ruling T2m M1, T12g m1): a
    fractional action is still an action the character spends, so the walk
    rounds the route's applications up ONCE; rounding each unit up overpriced a
    farm whose win yields more than a unit's worth of its cost."""
    kills = evidence.attempts_per_unit(monster_code, item, rate, min_q, max_q,
                                       fight_prospecting(monster_code, state, game_data))
    return kills * _kill_actions(monster_code, state, game_data, timing, records)


def _kill_actions(monster_code: str, state: WorldState, game_data: GameData,
                  timing: FightSecondsModel, records: Sequence[tuple[str, int, int]]) -> Fraction:
    """Whole-loop actions ONE win against `monster_code` costs, exact: the
    fight at its learned seconds plus the rest it forces (`cycles_per_kill`),
    and the learned losses expected per win (`_loss_surcharge`). The per-kill
    factor of every fight-priced route: a drop farm (`_drop_actions`) and a
    gold farm (`_priced`'s GOLD_DROP arm, which rounds up once per route, not
    per win: ruling T2m M1)."""
    fight = walk_seconds(state, game_data, monster_code, (), timing)
    per_kill = cycles_per_kill(
        expected_damage_per_fight(state, game_data, monster_code), state.max_hp, fight)
    return per_kill + _loss_surcharge(monster_code, state.max_hp, records, fight)


def _gather_actions(item: str, resource: str, state: WorldState, game_data: GameData,
                    evidence: LearnedDrops) -> Fraction:
    """Gathers of `resource` to obtain ONE `item`, exact: the attempts a unit
    takes (`LearnedDrops.attempts_per_unit`, spec 2026-10-18 §2.8) over the
    item's drop row (`GameData.gather_drop_row`), at the prospecting of the
    loadout the gather is made in (`gather_prospecting`), picked from the
    character's own holdings, a gear-objective price (`gear_objective._price`,
    ruling T14d-3) as much as an executor's. The SAME figure the planner's gather charges
    (`GatherAction.gathers`) and every gather source picker ranks by (ruling
    T16a), so the walk and the planner cannot disagree on a rare drop: 20
    `small_pearls` (1 in 300) off `trout_spot` are about 6,000 gathers under
    the prior (live 2026-10-19: the fleet fished 383 times for 2).

    A secondary drop is the case this exists for. `apple` drops off `ash_tree` at
    1 in 20, so a unit is 20 gathers; priced as one gather a unit — which every
    GATHER route once was, at `max_gather_yield` units an action — an apple
    looked as cheap as the tree's wood (live 2026-10-05: 554 gathers for 25
    apples). A sure primary drop of one unit is 1, its price unchanged.

    Exact, as a fight for gold is (ruling T2m M1): a learned chance is no whole
    number of gathers, and the walk rounds the route's applications up once."""
    rate, min_q, max_q = game_data.gather_drop_row(resource, item)
    return evidence.attempts_per_unit(resource, item, rate, min_q, max_q,
                                      gather_prospecting(resource, state, game_data))


def _priced(item: str, source: Source, state: WorldState,
            game_data: GameData, ctx: SelectionContext) -> RouteOption:
    """One `Source` plus its venue and action count.

    `Source.code` already means a different thing per kind (the resource, the
    NPC, the monster, the item to destroy — see `obtain_sources.Source`), and
    for GATHER, BUY and DROP that code IS the venue. CRAFT and RECYCLE happen at
    a workshop, WITHDRAW at a bank; those three are the only ones that need a
    venue derived rather than read."""
    if source.kind is SourceKind.WITHDRAW:
        return RouteOption(kind=source.kind.value, venue=BANK_VENUE,
                           actions_per_application=1, yield_per=source.yield_per,
                           capacity=source.capacity)
    if source.kind is SourceKind.RECYCLE:
        stats = game_data.item_stats(source.code)
        # `obtain_sources` already refused this source unless the item has a
        # crafting_skill, so the skill is present by that gate, not by luck.
        skill = stats.crafting_skill if stats is not None else ""
        return RouteOption(kind=source.kind.value, venue=_workshop_venue(skill or ""),
                           actions_per_application=1, yield_per=source.yield_per,
                           capacity=source.capacity,
                           inputs={source.code: 1})
    if source.kind is SourceKind.CRAFT:
        stats = game_data.item_stats(item)
        skill = stats.crafting_skill if stats is not None else ""
        recipe = game_data.crafting_recipe(item) or {}
        return RouteOption(kind=source.kind.value, venue=_workshop_venue(skill or ""),
                           actions_per_application=1, yield_per=source.yield_per,
                           capacity=source.capacity, inputs=dict(recipe))
    if source.kind is SourceKind.GATHER:
        return RouteOption(kind=source.kind.value, venue=source.code,
                           actions_per_application=_gather_actions(
                               item, source.code, state, game_data, ctx.drops()),
                           yield_per=1, capacity=source.capacity)
    if source.kind is SourceKind.SELL:
        npc_code, price = _sale_of(source.code, state, game_data)
        # One sale: one action, at the buyer's tile, yielding `price` gold and
        # consuming one copy of the item sold. `inputs` is what makes the walk
        # charge that copy — a sale is not free gold, it is gold at the cost of
        # whatever the copy cost, and a licensed surplus copy already in the bag
        # costs nothing because `owned` credits it.
        return RouteOption(kind=source.kind.value, venue=npc_code,
                           actions_per_application=1, yield_per=price,
                           capacity=source.capacity, inputs={source.code: 1})
    if source.kind is SourceKind.BUY:
        price, currency = npc_price_of(item, source.code, game_data)
        return RouteOption(kind=source.kind.value, venue=source.code,
                           actions_per_application=1, yield_per=source.yield_per,
                           capacity=source.capacity, inputs={currency: price})
    if source.kind is SourceKind.GE_FILL:
        price = ge_price_of(item, source.code, game_data)
        # `Source.code` is the ORDER id, not an item — the venue token is the
        # order because that is what `GeFillSellOrderAction` fills. Cost is gold
        # at the order's own price, which is what makes it REALIZABLE: we never
        # price a route at an order we would have to post and hope fills.
        return RouteOption(kind=source.kind.value, venue=source.code,
                           actions_per_application=1, yield_per=source.yield_per,
                           capacity=source.capacity, inputs={"gold": price})
    if source.kind is SourceKind.DROP:
        rate, min_q, max_q = _drop_table(item, source.code, game_data)
        return RouteOption(
            kind=source.kind.value, venue=source.code,
            actions_per_application=_drop_actions(item, source.code, rate, min_q,
                                                  max_q, state, game_data, ctx.timing(),
                                                  ctx.drops(), ctx.fight_records),
            yield_per=source.yield_per, capacity=source.capacity)
    if source.kind is SourceKind.GOLD_DROP:
        # Gold minted by fighting (ruling T2a): one application is one win
        # against the monster (`Source.code`), paying the route's expected gold,
        # the mean `(min_gold + max_gold) // 2` of the API's range
        # (`drop_routes.gold_drop_routes`). The walk takes `gold needed / mean
        # gold per kill` applications, each priced as a drop farm's kill is,
        # at its exact cost: the walk rounds the wins up once (ruling T2m M1).
        return RouteOption(
            kind=source.kind.value, venue=source.code,
            actions_per_application=_kill_actions(
                source.code, state, game_data, ctx.timing(), ctx.fight_records),
            capacity=source.capacity, yield_per=source.yield_per)
    if source.kind is SourceKind.TASK_REWARD:
        # The task board (ruling T2b): no API datum gives a task's length, so
        # the route is priced at the unpriced sentinel. It stays a route (the
        # item is achievable) and orders after every priced one; a length is
        # never invented.
        return RouteOption(kind=source.kind.value, venue=source.code,
                           actions_per_application=UNOBTAINABLE_PER_UNIT,
                           yield_per=source.yield_per, capacity=source.capacity)
    # DROP is now an EXPLICIT branch rather than the fallthrough it used to be.
    # As the fallthrough it silently swallowed every unclassified kind: adding
    # GE_FILL passed the entire gate and then broke the live bot on the first
    # plan, because a GE order id reached `_drop_table` as a monster code
    # ("no 6a803d67e8e9a9dd4ab01f5d drop row for battlestaff"). A new SourceKind
    # must now be priced deliberately or say so loudly.
    raise ValueError(  # pragma: no cover - every SourceKind above is handled
        f"{source.kind} has no pricing branch in `_priced` — add one rather than "
        "letting it fall through to another kind's arm")


def ge_price_of(item: str, order_id: str, game_data: GameData) -> int:
    """The gold price of the standing GE sell order `obtain_sources` named.

    Re-read for the same reason `npc_price_of` re-reads `npc_purchases`: `Source`
    carries only the order id. A missing row means the order book changed between
    two reads inside one decision, which cannot happen — so this raises rather
    than defaulting, per the API-data rule (CLAUDE.md: use only API data or fail).
    """
    order = game_data.ge_best_sell_order(item)
    if order is None or order[0] != order_id:
        raise KeyError(f"no standing GE sell order {order_id!r} for {item}")
    return order[1]


def npc_price_of(item: str, npc_code: str, game_data: GameData) -> tuple[int, str]:
    """`(price, currency)` this NPC charges for this item.

    `obtain_sources` produced the BUY source from the same `npc_purchases` table,
    so the row exists; the loop re-reads it because `Source` carries only the NPC
    code. A missing row would mean the two calls disagreed about game data
    between them, which cannot happen inside one decision — so this raises rather
    than defaulting, per the API-data rule."""
    for code, price, currency in game_data.npc_purchases(item):
        if code == npc_code:
            return price, currency
    raise KeyError(f"no {npc_code} purchase row for {item}")


def _sale_of(item: str, state: WorldState,
             game_data: GameData) -> tuple[str, int]:
    """`(npc, price)` for the best tradeable buyer of `item`.

    Same contract as `npc_price_of`, and the gates must be the SAME ones
    `ObtainModel._sell` applied — price, known location, and
    `event_npc_tradeable` — or the two would pick different buyers for one
    source and the venue would name an NPC the model never admitted. That is why
    `state` is threaded here rather than the item alone.

    A missing row would mean the two calls disagreed about game data inside a
    single decision, which cannot happen, so this raises rather than defaulting,
    per the API-data rule."""
    now = datetime.now(timezone.utc)
    for npc_code, price in game_data.npcs_buying_item(item):
        if price <= 0 or game_data.npc_location(npc_code) is None:
            continue
        if event_npc_tradeable(npc_code, game_data, x=state.x, y=state.y,
                               active_events=state.active_events, now=now):
            return npc_code, price
    raise KeyError(f"no tradeable buyer for {item}")


def _drop_table(item: str, monster_code: str,
                game_data: GameData) -> tuple[int, int, int]:
    """`(rate, min_quantity, max_quantity)` for this monster's drop of `item`.
    Same contract as `npc_price_of`: the row exists because `obtain_sources` built
    the DROP source from it."""
    for code, rate, min_q, max_q in game_data.monsters_dropping(item):
        if code == monster_code:
            return rate, min_q, max_q
    raise KeyError(f"no {monster_code} drop row for {item}")


def _gated_skill_option(item: str, state: WorldState, game_data: GameData,
                        store: LearningStore, evidence: LearnedDrops, model: ObtainModel,
                        kind: SourceKind, policy: Policy) -> RouteOption | None:
    """The CRAFT or GATHER route whose skill requirement is unmet, priced with
    the grind that would open it. `obtain_sources` withholds it under a policy
    that enforces the skill gate; under one that does not (`PIECE_POLICY`) it
    names the route as ready, and under `price_climbs` `route_options` drops
    that ready copy, so the climb is paid either way (ruling T2c'). A CRAFT route's
    gate is the crafting skill; a GATHER route's is the gathering skill, which
    `obtain_sources` enforces since D-A (docs/PLAN_decision_architecture_redesign.md):
    a resource the character cannot yet gather is no ready route, but it is
    a PRICED one here, by the same grind rule.

    THE SEAM, STATED OUT LOUD. `obtain_sources` answers READINESS: what can the
    executor serve *right now*. A skill-gated craft genuinely cannot be served
    right now, so excluding it there is correct. This module answers a different
    question — what would it COST to obtain this — and that answer may include
    making a route ready. The gate is a price, not a wall.

    That distinction is real, but it is also how a second route model creeps
    back in, which is the thing this epic exists to kill. So the routes this
    module adds are only ever the obtain model's OWN routes that one gate keeps
    closed (`ObtainModel.gated_by`), each carrying its `unlock`, and a census
    pins that (`test_the_pricer_adds_nothing_but_gated_routes`).

    `None` — no route at all — only when a grind could not open the craft anyway.
    The route is the obtain model's CRAFT route that the crafting-skill gate
    ALONE keeps from being ready (`ObtainModel.gated_by`), so there is none when:

      * the item is not craftable, or names no crafting skill;
      * the gate is already MET (then `obtain_sources` names the craft itself,
        and adding a second copy would double the route);
      * no workshop is known (a grind cannot conjure a bench, so paying it would
        buy nothing: the route is then blocked by a second gate).

    AN UNPRICEABLE GRIND DECLINES THE ROUTE. It briefly charged 0 instead, on
    the argument that this is a LOWER bound and omitting an unknown positive term
    is the safe direction. That argument is correct about PRUNING and wrong about
    RANKING, and `J` does both: a bound used as a ranking key systematically
    prefers whatever is most under-priced.

    Measured live, 2026-08-08: with the grind priced from a rate that was 50-100x
    too high, `greater_wooden_staff` showed `acquire_cost=68` for a
    weaponcrafting 6->10 grind, `J` committed, and R2D2 spent 4.5 HOURS running
    207 `LevelSkill` actions for +270 skill xp and ZERO character xp. HAL did the
    same. A free-looking grind does not merely fail to prune — it captures the
    bot.

    So: no observations anywhere in the fleet, a non-positive observed rate, or
    no `<skill>_max_xp` from the API all decline the route. A non-positive rate is
    EVIDENCE the grind is not progressing, which is a stronger reason to decline
    than ignorance is. Declining costs the character that one route, not its
    progress — every other root still competes.

    THE RATE COMES FROM THE GRIND'S OWN CYCLES (2026-08-18). It used to come from
    `skill_xp_per_cycle_all`, which averages over the last 100 cycles of ANY
    activity — so a character spending its recent cycles fighting read 0.0 and
    this route was declined for every skill-gated craft it could ever want.
    Measured live: all five characters, all four crafting skills, exactly 0.0, and
    every iron-tier item consequently priced at `UNOBTAINABLE_PER_UNIT` while the
    gearcrafting grind that would open it was itself unrankable. Those are the
    same fact — the price forbade the grind and the absent grind kept the price.
    `skill_grind_rate` limits to cycles whose `action_repr` is this skill's
    `LevelSkill`, so a grind in progress feeds the estimate that prices it."""
    gated = _skill_gated(item, model, kind, policy)
    if gated is None:
        return None
    route, skill, level = gated
    # OWN evidence first, the fleet's only in its ABSENCE. `None` means this
    # character has never ground this skill; `0.0` means it ground it and gained
    # nothing, which is a fact about ITS gear and level that a sibling's number
    # must not paper over. The `is None` test is therefore load-bearing and must
    # not become a falsy test — `rate or fleet` would silently make a stuck
    # character borrow a healthy one's rate.
    rate = store.skill_grind_rate(skill)
    if rate is None:
        rate = store.fleet_skill_grind_rate(skill)
    max_xp = state.skill_max_xp.get(skill, 0)
    if not rate or rate <= 0 or max_xp <= 0:
        return None
    grind = skill_grind_cycles(
        state.skills.get(skill, 1), state.skill_xp.get(skill, 0),
        max_xp, level, rate)
    if kind is SourceKind.GATHER:
        return RouteOption(
            kind=kind.value, venue=route.via,
            actions_per_application=_gather_actions(item, route.via, state, game_data, evidence),
            yield_per=1, capacity=UNBOUNDED_CAPACITY,
            unlock=f"skill:{skill}:{level}", unlock_actions=grind)
    return RouteOption(
        kind=SourceKind.CRAFT.value, venue=_workshop_venue(skill),
        actions_per_application=1, yield_per=route.yield_per,
        capacity=UNBOUNDED_CAPACITY, inputs=dict(route.inputs),
        unlock=f"skill:{skill}:{level}",
        unlock_actions=grind,
    )


_SKILL_GATE = {SourceKind.CRAFT: GateKind.CRAFT_SKILL, SourceKind.GATHER: GateKind.GATHER_SKILL}
"""The skill gate on each route kind a grind can open."""


def _climbing(policy: Policy) -> Policy:
    """The policy a PRICE reads a skill requirement under. With `price_climbs`
    (ruling T2c'), `policy` with both skill gates enforced: a route whose own
    skill requirement exceeds the character's skill costs the climb to it,
    whether or not `policy` refuses the route for it, so the gate flag decides
    achievability, not price. Without it, `policy` itself: a gate the policy
    opens on purpose prices as the ready route."""
    if not policy.price_climbs:
        return policy
    return replace(policy, gather_skill_gate=True, craft_skill_gate=True)


def _climbs(item: str, model: ObtainModel, policy: Policy) -> frozenset[tuple[SourceKind, str]]:
    """`(kind, via)` of every CRAFT or GATHER route to `item` that its own skill
    requirement alone keeps closed (`_climbing`). Such a route is never priced
    as ready: `route_options` prices it with its climb, or not at all. Empty
    without `price_climbs`, by return: a route a gate keeps closed is then one
    `policy` itself refuses, so `obtain_sources` never names it, and there is
    nothing to drop (ruling T2m M2)."""
    if not policy.price_climbs:
        return frozenset()
    return frozenset((route.kind, route.via)
                     for kind, gate_kind in _SKILL_GATE.items()
                     for route in model.gated_by(item, _climbing(policy), gate_kind)
                     if route.kind is kind)


def _skill_gated(item: str, model: ObtainModel, kind: SourceKind,
                 policy: Policy) -> tuple[Route, str, int] | None:
    """`(route, skill, level)` for the first `kind` route to `item` that its
    skill requirement alone keeps closed (`_climbing(policy)`), or None. Under
    `price_climbs` the requirement is the route's own, read whether or not
    `policy` enforces the gate: a policy that admits the route as ready still
    pays the climb. Otherwise only a gate `policy` enforces is a climb."""
    gate_kind = _SKILL_GATE[kind]
    for route in model.gated_by(item, _climbing(policy), gate_kind):
        if route.kind is kind:
            [gate] = [g for g in route.gates if g.kind is gate_kind]
            assert gate.level is not None, f"{item!r}: a skill gate carries its level"
            return route, gate.subject, gate.level
    return None


def _sibling_craft_option(item: str, state: WorldState, game_data: GameData,
                          ctx: SelectionContext,
                          store: LearningStore, model: ObtainModel,
                          policy: Policy) -> RouteOption | None:
    """A LIVE SIBLING already clears the crafting gate this character does not.

    The third deferred route, and it sits here for the same reason
    `_gated_skill_option` does: `obtain_sources` answers "what can I do RIGHT
    NOW" and its eligibility mirrors the action pool, but no action a character
    can plan this cycle makes a sibling craft something. Modelling it as a
    seventh `SourceKind` — which `PLAN_iron_gear_acquisition.md` increment 4
    recommended — would have produced a source with no action in existence to
    serve it, exactly what `ObtainModel._withdraw`'s `bank_accessible` gate exists to
    prevent, and the obtain-parity census would have been right to reject it.
    `RouteOption.unlock` is already the mechanism for "a prerequisite this route
    must satisfy before its first application", so this is one more instance of
    it rather than a new concept.

    The gate must ALREADY be met by the sibling. A sibling that could grind
    toward the skill is not a route, for the same reason a GE order we could POST
    is not one: both are work nobody has committed to, and pricing speculation is
    how a route model starts lying. "One craft away" is the whole claim.

    The requester still owes the MATERIALS — `inputs` is the recipe, unchanged
    from a normal craft, and `acquisition_options` follows it transitively. What
    a sibling saves is strictly the SKILL GATE, which is exactly the asymmetry
    `MaterialDemand.self_servable` already encodes ("ASYMMETRY IS STRICTLY ABOUT
    SKILL GATES").

    The unlock is keyed on the ITEM rather than the skill because that is what a
    request is for: two items behind the same sibling skill are two requests, and
    two units of one item are one. `unlock_actions` is paid once across every
    route sharing the key, which is precisely the batching `SupplyClaim` elects a
    single producer to perform.

    NO SIBLING MEETS THE GATE YET (spec 2026-10-18 §2.5): the fleet's ONE
    climber for the skill (`fleet_climber.fleet_climbers`) pays the climb once
    for every fleet unit it unlocks, so the route still exists, with the
    climber's remaining climb divided across those units
    (`_amortized_fleet_climb`) added to the request cost. "Speculation" above
    meant a climb nobody committed to; this climber is committed — the fleet
    assigned it the skill (ruling T7a), it holds or is free to claim the
    skill's role, and the role's objective serves every fleet piece the climb
    unlocks (`fleet_pieces`). A climber holding another role serves none, so
    it is not on `ctx.fleet_climbers` and the route does not exist. When this
    character IS the climber there is no sibling route: its own climb is
    `_gated_skill_option`.
    """
    gated = _skill_gated(item, model, SourceKind.CRAFT, policy)
    if gated is None:
        return None  # no craft, or our own CRAFT route already covers it
    route, skill, level = gated
    cost = store.fleet_supply_request_cycles()
    if cost is None or cost <= 0:
        return None  # the fleet has never served a request; nothing to price it with
    climb = 0
    if ctx.sibling_skills.get(skill, 0) < level:
        # Nobody is one craft away: the fleet's climber climbs for us.
        amortized = _amortized_fleet_climb(skill, level, state, game_data, ctx, store)
        if amortized is None:
            return None
        climb = amortized
    return RouteOption(
        kind=SourceKind.CRAFT.value, venue=BANK_VENUE,
        actions_per_application=1, yield_per=route.yield_per,
        capacity=UNBOUNDED_CAPACITY, inputs=dict(route.inputs),
        unlock=f"sibling:{item}",
        unlock_actions=climb + int(cost),
    )


def climber_rate(store: LearningStore, who: str, skill: str) -> float | None:
    """The xp a cycle `who` grinds `skill` at: its own rate, the fleet's only in
    its ABSENCE (the load-bearing `is None` test), or None when neither is
    positive. The one rate the climb is priced with (`_amortized_fleet_climb`)
    and the fleet's climbers are ranked by (`fleet_climber.fleet_climbers`,
    ruling T14d-6)."""
    rate = store.character_skill_grind_rate(who, skill)
    if rate is None:
        rate = store.fleet_skill_grind_rate(skill)
    return rate if rate is not None and rate > 0 else None


def _amortized_fleet_climb(skill: str, level: int, state: WorldState, game_data: GameData,
                           ctx: SelectionContext, store: LearningStore) -> int | None:
    """This character's share, in actions, of the fleet climber's remaining
    climb of `skill` to `level` (spec 2026-10-18 §2.5), or None when there is
    no sibling climb to share: the fleet names no SERVING climber for the skill
    (`ctx.fleet_climbers`: the assigned climbers that hold or are free to
    claim the skill's role; empty without a fleet or on a failed ledger read),
    this character is the climber itself, or the climb cannot be priced.

    The remaining climb is priced as `decisions/route.route_price` prices a
    `ReachSkillLevel`: `skill_grind_cycles` at the climber's grind rate
    (`character_skill_grind_rate`), the fleet's only in its ABSENCE (the same
    load-bearing `is None` test), and a non-positive rate or xp requirement
    declines. Cycles ARE actions, so no conversion follows. The ledger
    publishes levels, not xp, so the climber climbs from the start of its
    level, and this character's own `skill_max_xp` stands for every level —
    `skill_grind_cost_core`'s own assumption, a lower bound on a rising curve.

    Shared across the units it unlocks (`amortized_climb_seconds`, rounded up
    to whole actions): the one being priced, plus every unit of a sibling's
    `L*` piece on the board that `skill` gates above the climber's level and
    at or below `level` — the climb to `level` opens exactly those."""
    who = ctx.fleet_climbers.get(skill)
    if who is None or who == state.character:
        return None
    rate = climber_rate(store, who, skill)
    max_xp = state.skill_max_xp.get(skill, 0)
    if rate is None or max_xp <= 0:
        return None
    start = ctx.sibling_skill_ledger[who].get(skill, 0)
    remaining = skill_grind_cycles(start, 0, max_xp, level, rate)
    units = 1
    for code, (asked, _gain) in ctx.fleet_board.items():
        requirement = game_data.producing_requirement(code)
        if requirement is not None and requirement[0] == skill and start < requirement[1] <= level:
            units += asked
    return ceil(amortized_climb_seconds(Fraction(remaining), units))


def _gated_drop_option(item: str, state: WorldState, game_data: GameData,
                       ctx: SelectionContext,
                       store: LearningStore | None, model: ObtainModel,
                       policy: Policy) -> RouteOption | None:
    """The DROP route `obtain_sources` withholds because the dropper is
    UNWINNABLE — priced with the gear that would open the fight.

    THE SAME SEAM `_gated_skill_option` STATES: `obtain_sources` answers
    READINESS, and a monster this character loses to genuinely cannot be farmed
    right now, so excluding it there is correct. This module answers what it
    would COST, and that answer may include making the route ready. The gate is
    a price, not a wall.

    The 2026-08-09 exclusion audit ranked this the biggest of its six walls and
    could not fix it: *"cost to become able to beat monster X has no simple
    measure and is circular"*. `combat_deficit` is the measure — a gear chain
    plus a `closes` verdict — and the circularity is handled below rather than
    reasoned away.

    MEASURED BEFORE IT WAS BUILT (`audit/drop_wall_census.py`, 2026-08-28): 9
    candidate roots on the committed bundle price at `UNOBTAINABLE_PER_UNIT`
    purely because their dropper is unbeatable, all nine on ALTERNATIVES rather
    than on a resolved root, and `combat_deficit` closes 9 of 9 with a ONE-ITEM
    chain — `cowhide`<-cow needs `iron_sword`, `mushroom`<-mushmush needs
    `forest_whip`. The wall is real, and it is shallow.

    THE RECURSION IS CUT BY CONSTRUCTION, NOT BY A DEPTH BUDGET. Pricing the
    chain re-enters this module, and a chain item whose own recipe wants a
    drop-walled material would re-enter this gate — `cowhide` needs `iron_sword`
    needs a drop that needs gear, without end. So the chain is priced with
    `gated_drop=False`: one level of gate, and the inner walk sees exactly the
    routes `obtain_sources` serves today. That is a strict UNDER-count of what a
    fully-recursive model would allow, which is the safe direction for a bound,
    and it terminates without a fuel counter to tune.

    AN UNPRICEABLE CHAIN DECLINES THE ROUTE, exactly as an unpriceable grind does
    one function up, and for the live reason recorded there: a route that looks
    free does not merely fail to prune, it CAPTURES the bot (R2D2, 4.5 hours, 207
    `LevelSkill` actions for zero character xp). A chain step that prices at
    `UNOBTAINABLE_PER_UNIT` means the gear itself is out of reach, so the fight
    behind it is too.

    `None` — no route to add — whenever the gate is not this function's business:

      * nothing drops the item, or no dropper stands on a live tile (then there
        is no DROP route to unlock, and `ObtainModel._drop` is right to be silent);
      * no live dropper's deficit CLOSES (`combat_deficit`'s own "unwinnable and
        I do not know what to build" — an honest wall, and the census's
        `WALL_DROPPER_OUT_OF_REACH` arm);
      * the closing chain cannot be priced.

    "SOME LIVE DROPPER IS WINNABLE" IS NOT CHECKED HERE, deliberately, though it
    is the one case that would double-price a route. The caller asks this
    function only when NOTHING serves the item, and a winnable live dropper IS a
    served DROP route — so the condition cannot hold at this point, and a guard
    for it would be the second of two guards where one is correct. This module
    has been bitten by that shape before: `acquisition_options` once filtered at
    both push and pop, which made the pop guard unreachable and hid that the
    other was doing nothing.

    The unlock is keyed on the MONSTER, not the item: two materials behind one
    unbeatable monster are unlocked by one gear acquisition, and `unlock_actions`
    is paid once across every route sharing the key. Keying it on the item would
    charge the sword once per material the cow drops."""
    rested = replace(state, hp=state.max_hp)
    # The obtain model's DROP routes that winnability ALONE keeps closed: a
    # live dropper this character cannot beat (`ObtainModel.gated_by`).
    live = [route.via for route in model.gated_by(item, policy, GateKind.WINNABLE)
            if route.kind is SourceKind.DROP]
    if not live:
        return None
    best: RouteOption | None = None
    for monster in live:
        deficit = combat_deficit(rested, game_data, monster)
        if deficit is None or not deficit.closes:
            continue
        unlock_actions = 0
        for step in deficit.chain:
            unlock_actions += acquisition_actions(
                step.code, 1, state, game_data, ctx, equip=True, store=store,
                gated_drop=False, policy=policy)
        if unlock_actions >= UNOBTAINABLE_PER_UNIT:
            continue
        rate, min_q, max_q = _drop_table(item, monster, game_data)
        # No loss surcharge: the learned record is about the loadout this gear
        # chain replaces, and a different loadout is a different fight.
        option = RouteOption(
            kind=SourceKind.DROP.value, venue=monster,
            actions_per_application=_drop_actions(
                item, monster, rate, min_q, max_q, state, game_data, ctx.timing(),
                ctx.drops()),
            yield_per=1, capacity=UNBOUNDED_CAPACITY,
            unlock=f"gear:{monster}", unlock_actions=unlock_actions)
        # CHEAPEST BY THE WHOLE PRICE, not by the unlock alone: a dear sword that
        # opens a monster dropping the item every kill beats a cheap one that
        # opens a 1-in-200 drop. Both terms are what a plan actually pays.
        if best is None or (option.unlock_actions + option.actions_per_application
                            < best.unlock_actions + best.actions_per_application):
            best = option
    return best


def route_options(item: str, state: WorldState, game_data: GameData,
                  ctx: SelectionContext,
                  store: LearningStore | None = None,
                  gated_drop: bool = True, *, policy: Policy = LEGACY) -> list[RouteOption]:
    """Every route to `item`, priced: the ones `obtain_sources` names, less any
    whose own skill requirement is unmet, plus — only when a `store` is
    supplied — the skill-gated craft or gather priced with its climb.

    `store` defaults to None so every existing caller keeps today's behaviour
    exactly. Neither deferred route can be priced without the store: a gated
    craft needs an observed grind rate, and a sibling craft needs the observed
    cost of a fleet supply request."""
    model = ObtainModel(state, game_data, ctx, datetime.now(timezone.utc))
    # A route its own skill requirement keeps closed is priced only with its
    # climb (`_gated_skill_option`, ruling T2c), never as the ready route a
    # policy without the skill gate names it.
    climbs = _climbs(item, model, policy)
    routes = [_priced(item, s, state, game_data, ctx)
              for s in obtain_sources(item, state, game_data, ctx, policy=policy)
              if (s.kind, s.code) not in climbs]
    if store is not None:
        for kind in (SourceKind.CRAFT, SourceKind.GATHER):
            gated = _gated_skill_option(item, state, game_data, store, ctx.drops(), model,
                                        kind, policy)
            if gated is not None:
                routes.append(gated)
        sibling = _sibling_craft_option(item, state, game_data, ctx, store, model, policy)
        if sibling is not None:
            routes.append(sibling)
    # OUTSIDE the store gate, unlike its two siblings, and deliberately: their
    # unlocks are priced from OBSERVATION (a learned grind rate, an observed
    # fleet request cost) and cannot be sized at all without a store, while this
    # one reads the catalogue and the combat model, both deterministic.
    #
    # THE STORE DEPENDENCY IS TRANSITIVE, NOT DIRECT, and measured: on the
    # committed bundle every one of the nine walled cells is unlocked by gear
    # whose own craft is skill-gated, so without a grind rate
    # `_gated_skill_option` declines the gear, the gear prices at infinity and
    # this gate declines the fight behind it. A chain that is already craftable
    # needs no store — which is why the gate belongs here and not behind
    # `store is not None`, where a store-less caller could never see it fire even
    # when nothing observational is missing.
    #
    # ASKED ONLY WHEN NOTHING SERVES THE ITEM TODAY (`not routes`): "walled"
    # MEANS the item has no route, so an item that has one is not this gate's
    # subject and a second, dearer route for it is noise. The cost of the test is
    # a route that might have undercut an existing expensive one — an UNDER-count,
    # the safe direction for a bound and the same direction the one-level chain
    # cut already takes.
    #
    # IT IS NOT A SPEED OPTIMISATION, and was measured rather than assumed: the
    # sweep costs the same either way (29s -> 41s over 438 candidate price walks,
    # +43%, with or without this test). The items it skips were already exiting
    # cheaply; the cost lives in the walled items themselves, which are exactly
    # the ones this test keeps.
    if gated_drop and not routes:
        drop = _gated_drop_option(item, state, game_data, ctx, store, model, policy)
        if drop is not None:
            routes.append(drop)
    return routes


_PRODUCING = frozenset({SourceKind.CRAFT.value, SourceKind.GATHER.value})
"""The route kinds that MAKE an item: the only routes a `produce` item keeps."""


def acquisition_options(item: str, state: WorldState, game_data: GameData,
                        ctx: SelectionContext,
                        store: LearningStore | None = None,
                        gated_drop: bool = True, *, policy: Policy = LEGACY,
                        produce: frozenset[str] = frozenset()
                        ) -> dict[str, list[RouteOption]]:
    """`route_options` over the whole closure reachable from `item`.

    The closure follows each route's INPUTS — recipe materials, recycle sources,
    and purchase CURRENCIES alike — so a vendor item priced in `event_ticket`
    pulls in however the tickets themselves are obtained. That currency edge is
    the one `min_plan_length` has no way to represent, and following it is what
    makes a 100-ticket purchase cost more than a free one.

    Cyclic by nature, not by accident: `copper_bar` recycles out of a
    `copper_dagger`, which crafts from `copper_bar`. So the walk needs a visited
    set, and it is checked at POP and nowhere else. An earlier version also
    filtered at push, which made the pop guard unreachable — two guards where
    one is correct, and the redundant one hid the fact that the other was doing
    nothing. The cost walk's own fuel bound handles the cycle when it comes to
    PRICE it; this only has to enumerate.

    `produce` names items that must be MADE (ruling T12j), as
    `ObtainModel.walk_graph` takes it: only their CRAFT and GATHER routes are
    priced. A skill grind's rung earns its XP in the craft, so buying it, filling
    it on the GE, withdrawing it or taking it as a drop is no price of the rung;
    its ingredients keep every route."""
    options: dict[str, list[RouteOption]] = {}
    frontier = [item]
    while frontier:
        code = frontier.pop()
        if code in options:
            continue
        routes = route_options(code, state, game_data, ctx, store, gated_drop, policy=policy)
        if code in produce:
            routes = [route for route in routes if route.kind in _PRODUCING]
        options[code] = routes
        for route in routes:
            frontier.extend(route.inputs)
    return options


def _owned_with_gold(state: WorldState, pocket: int) -> dict[str, int]:
    """The bag, plus `pocket` gold: the gold in it the caller lets the price
    spend (the whole pocket, or only what the reserve lets a piece's buy
    spend: `progression_reserve.spendable_pocket`, ruling T3e m3).

    A gold-priced BUY route carries `inputs={"gold": price}` and the walk prices
    an input it cannot obtain at `UNOBTAINABLE_PER_UNIT` PER UNIT — so without
    this, every gold-priced vendor route in the game was charged
    `price * 1,000,000` actions. Measured live: `lifesteal_rune` at 20,000 gold
    priced at 20,000,000,002 instead of 2, and 46 item/vendor pairs are sold for
    gold. Nothing obtains gold, so nothing could ever pay that down; the route
    was not expensive, it was unreachable.

    POCKET ONLY, and that follows the bag-only rule this module already states:
    the bank is a ROUTE, not a holding. Banked gold is therefore not credited
    here, which is conservative — it under-credits rather than pricing a trip to
    the bank at nothing. Making banked gold a withdraw route of its own is a
    separate increment (`WithdrawGoldAction` exists and is dormant precisely
    because no goal has ever needed banked gold — which is what this wall did)."""
    owned = dict(state.inventory)
    owned["gold"] = owned.get("gold", 0) + pocket
    return owned


def cheapest_route(item: str, qty: int, state: WorldState, game_data: GameData,
                   ctx: SelectionContext, store: LearningStore | None,
                   gated_drop: bool = True, *, policy: Policy, pocket: int,
                   credit_skills: frozenset[str] = frozenset(),
                   produce: frozenset[str] = frozenset()) -> tuple[int, SourceKind | None]:
    """`(price, route)`: the lower bound on planner actions to obtain `qty` of
    `item` (`acquisition_actions` without the equip), and the kind of the route
    that price takes for `item` itself (plan B Task 3: a piece is served by the
    route that priced it).

    The route is the argmin of `item`'s `acquisition_options`, first of equal
    prices as `acquisition_cost` takes it (`priced_route`). An item whose only
    routes are climbs no grind rate can price (no store, or no observed rate)
    has no priced route, and is priced at the no-route sentinel; its route is
    then the climb's own kind, CRAFT before GATHER, as `route_options` would
    have priced it. None only when the item has no route at all.

    Held gold is free up to `pocket` (ruling T2k, `_owned_with_gold`): the
    choice credits it as the walk does, so a fill or a buy the pocket covers
    is not priced at gold's fight cost against a dearer craft. A piece's
    price passes the pocket above the reserve its buy must keep (ruling T3e
    m3), so gold the executor will not spend is priced as gold to earn."""
    owned: dict[str, int] = _owned_with_gold(state, pocket)
    options: Mapping[str, list[RouteOption]] = credit_demanded_skills(
        acquisition_options(item, state, game_data, ctx, store, gated_drop, policy=policy,
                            produce=produce),
        credit_skills, game_data)
    price, route = priced_route(item, qty, options, owned, frozenset({GOLD_CODE}))
    if route is not None:
        return price, _served_by(route)
    model = ObtainModel(state, game_data, ctx, datetime.now(timezone.utc))
    for kind in _SKILL_GATE:
        if _skill_gated(item, model, kind, policy) is not None:
            return price, kind
    return price, None


_DROP_WORK = frozenset({SourceKind.GATHER.value, SourceKind.DROP.value})
"""The route kinds whose work is attempts at a drop chance: a gather and a
fight for an item drop. Prospecting raises that chance (spec 2026-10-18 §2.8);
a fight for gold pays its range, not a chance, so it is no drop work."""


def drop_work(item: str, qty: int, state: WorldState, game_data: GameData,
              ctx: SelectionContext, store: LearningStore | None, *,
              policy: Policy) -> tuple[DropLeg, ...]:
    """The remaining drop work of the route that prices `qty` of `item`: a
    `DropLeg` for every gather and drop-farm leg the walk takes
    (`acquisition_cost_core.route_legs`), carrying the route's own kind and
    whether its wins carry the loss surcharge (a farm behind gear, keyed
    `gear:<monster>`, does not: `_gated_drop_option`). The walk is
    `cheapest_route`'s own, over the same options and holdings (the bag, plus
    the pocket's gold), so the work is the work the price is made of."""
    options = acquisition_options(item, state, game_data, ctx, store, policy=policy)
    legs = route_legs(item, qty, options, _owned_with_gold(state, state.gold),
                      frozenset({GOLD_CODE}))
    return tuple(DropLeg(SourceKind(route.kind), route.venue, code, units,
                         surcharged=not route.unlock)
                 for code, route, units in legs if route.kind in _DROP_WORK)


def drop_work_actions(work: Sequence[DropLeg], state: WorldState,
                      game_data: GameData, ctx: SelectionContext) -> Fraction:
    """Actions `work` (`drop_work`'s legs) takes, exact: each leg's units
    times the per-unit price its route has in the walk — a farm's
    (`_drop_actions`, with the loss surcharge only where the walk charges it)
    or a gather's (`_gather_actions`) — so at the prospecting of the loadout
    the leg is attempted in, exactly as the walk prices it: an item that
    loadout would not wear moves no price. Both read the ONE drop model
    (`ctx.drops()`)."""
    total = Fraction(0)
    for leg in work:
        if leg.kind is SourceKind.DROP:
            rate, min_q, max_q = _drop_table(leg.item, leg.source, game_data)
            per_unit = _drop_actions(leg.item, leg.source, rate, min_q, max_q, state,
                                     game_data, ctx.timing(), ctx.drops(),
                                     ctx.fight_records if leg.surcharged else ())
        else:
            per_unit = _gather_actions(leg.item, leg.source, state, game_data, ctx.drops())
        total += leg.units * per_unit
    return total


def _served_by(route: RouteOption) -> SourceKind:
    """The route kind that SERVES `route` on this character's side. A
    sibling's craft (`_sibling_craft_option`: CRAFT at `BANK_VENUE`) reaches
    this character as a bank WITHDRAW — the sibling crafts and banks it, and
    this character's own step is the withdraw (spec 2026-10-18 §2.5,
    "Delivery") — so a piece it priced is never served by this character's own
    craft, whose crafting gate would turn it into the very climb the sibling
    route exists to spare. Every other route serves as its own kind."""
    if route.kind == SourceKind.CRAFT.value and route.venue == BANK_VENUE:
        return SourceKind.WITHDRAW
    return SourceKind(route.kind)


def fight_gold_monster(state: WorldState, game_data: GameData, ctx: SelectionContext,
                       *, policy: Policy) -> str | None:
    """The monster a price under `policy` fights for gold: the argmin of
    gold's fight routes (`priced_route` over its GOLD_DROP routes only), the
    exact cost per gold of each win (ruling T2m M1), first of equal costs. A
    piece priced through fight gold is served by fighting this monster (plan
    B Task 15: served by the route that priced it). None only when no fight
    pays gold under `policy`.

    Fight routes only (ruling T15e): when a sale is gold's cheapest route, the
    walk's GOLD_DROP leg is still a fight, and it fights the monster the price
    would have, the cheapest fight. A choice over every route would name no
    monster then, and the piece would be declined every cycle a licensed
    surplus sells.

    The route a price picks for gold is gold's own choice, whatever is bought
    with it and however much (`_cheapest_route` is per unit, memoised per
    item), so it is the one inside every piece's price. No store: a gold
    route's price reads the timing model and the fight records on `ctx`, not
    an observed rate."""
    options = acquisition_options(GOLD_CODE, state, game_data, ctx, None, policy=policy)
    fights = {**options, GOLD_CODE: [route for route in options.get(GOLD_CODE, [])
                                     if route.kind == SourceKind.GOLD_DROP.value]}
    _price, route = priced_route(GOLD_CODE, 1, fights, {})
    return None if route is None else route.venue


def acquisition_actions(item: str, qty: int, state: WorldState,
                        game_data: GameData, ctx: SelectionContext,
                        equip: bool,
                        store: LearningStore | None = None,
                        gated_drop: bool = True, *, policy: Policy = LEGACY,
                        credit_skills: frozenset[str] = frozenset(),
                        produce: frozenset[str] = frozenset()) -> int:
    """Lower bound on planner actions to obtain (and optionally equip) `qty` of
    `item`, over every route the executor can currently serve.

    Drop-in shape for `min_plan_length`'s call sites, with `state`/`ctx` added
    because routes are STATE-AWARE — which is the whole point, and also the
    reason `acquisition_cost_core.UNOBTAINABLE_PER_UNIT` must never be cached
    across cycles.

    HOLDINGS ARE THE BAG ONLY, AND THAT IS A CHANGE. `min_plan_length`'s callers
    pass inventory PLUS bank, because that model has
    no withdraw action and so must treat a banked copy as already in hand. Here
    the bank is a ROUTE — `SourceKind.WITHDRAW`, capacity = the bank's stock —
    so counting it as owned too would credit the same copy twice and price the
    trip to the bank at nothing. A banked item costs one hop plus one withdraw,
    which is what it costs.

    `credit_skills` — routes training one of these skills cost no actions
    (`skill_credit`); empty by default, so every existing caller is unchanged.
    `produce` — items priced only by making them (`acquisition_options`).

    The price is `cheapest_route`'s, so there is one pricer."""
    price, _route = cheapest_route(item, qty, state, game_data, ctx, store, gated_drop,
                                   policy=policy, pocket=state.gold,
                                   credit_skills=credit_skills, produce=produce)
    return price + (EQUIP_ACTIONS if equip else 0)


def bundle_acquisition_actions(
        roots: Sequence[tuple[str, int]], state: WorldState, game_data: GameData,
        ctx: SelectionContext, equip: bool,
        store: LearningStore | None = None) -> tuple[int, dict[str, int]]:
    """`acquisition_actions` over SEVERAL roots as one plan: `(total, paid)`.

    The routes are the union of each root's closure. Merging is a plain update
    because `route_options` is a function of the ITEM and the state, so two roots
    that reach the same code reach the same routes for it — the union cannot
    disagree with either part.

    ANALYSIS ONLY. Nothing in the decision path calls this; it exists so
    `objective --bundle-price` can measure what a shared prerequisite is worth,
    which is the question that separates option C from option B in
    `docs/PLAN_bounded_horizon_objective.md`. Keeping it out of the pricer's
    hot path is deliberate — `J` compares candidates one at a time today, and
    making it compare bundles is the epic, not a diagnostic.

    `equip` is charged PER ROOT, not once: every piece has to be put on."""
    owned: dict[str, int] = _owned_with_gold(state, state.gold)
    options: dict[str, list[RouteOption]] = {}
    for item, _qty in roots:
        options.update(acquisition_options(item, state, game_data, ctx, store))
    total, paid = bundle_acquisition_cost(roots, options, owned)
    return total + (EQUIP_ACTIONS * len(roots) if equip else 0), paid

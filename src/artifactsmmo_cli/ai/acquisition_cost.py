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
from fractions import Fraction
from math import ceil

from artifactsmmo_cli.ai.acquisition_cost_core import (
    RouteOption,
    acquisition_cost,
    bundle_acquisition_cost,
)
from artifactsmmo_cli.ai.equipment.loadout_cache import pick_loadout_cached
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.expected_damage import expected_damage_per_fight
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_value_core import Rank
from artifactsmmo_cli.ai.learning.fight_loop_cost import cycles_per_kill
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.monster_drop_selection import (
    MonsterDropCandidate,
    expected_kills,
)
from artifactsmmo_cli.ai.obtain_sources import (
    UNBOUNDED_CAPACITY,
    Source,
    SourceKind,
    obtain_sources,
)
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.skill_grind_cost_core import skill_grind_cycles
from artifactsmmo_cli.ai.world_state import WorldState

BANK_VENUE = "bank"
"""Venue code for a bank tile. A constant rather than a per-tile code because
every bank serves the same withdraw, so two withdraws pay one hop between them —
which is what the character actually does."""

EQUIP_ACTIONS = 1
"""One `EquipAction`. Carries no venue: equipping happens wherever the character
is standing."""


def _workshop_venue(skill: str) -> str:
    """Workshop tiles are keyed by SKILL, so two crafts on the same skill pay one
    hop and a jewelry craft after a weapon craft pays two. Prefixed so a skill
    named like an NPC cannot collide with one."""
    return f"workshop:{skill}"


def _prospecting_relief(prospecting: int) -> Fraction:
    """Factor by which prospecting reduces expected kills per unit dropped.

    The server grants "1% extra per 10 prospecting", so the drop chance is scaled
    by `(1000 + prospecting) / 1000` and the kills needed are scaled by its
    RECIPROCAL. Mirrors `MonsterCatalog.xp_per_kill`'s wisdom term exactly
    (`(1000 + wisdom) / 1000`) rather than restating the rate — one place decides
    what "1% per 10 points" means, so the two cannot drift.

    Exact `Fraction`, never a float: this multiplies a `Fraction` that
    `Formal.MonsterDropSelection` proves things about, and a float here would
    quietly make that proof about a different number.

    THIS IS WHY PROSPECTING WAITED FOR INCREMENT 2. Its entire value is making a
    DROP farm cheaper, and until the drop route was priced at all there was
    nothing for it to reduce. Pricing the stat first would have given it a
    coefficient on zero."""
    return Fraction(1000, 1000 + prospecting)


def _expected_kills_per_unit(item: str, monster_code: str, rate: int, min_q: int,
                             max_q: int, prospecting: int,
                             store: LearningStore | None) -> Fraction:
    """Kills needed for ONE unit, from OBSERVATION where there is enough of it.

    THE TWO CORRECTIONS ARE ONE CORRECTION. The server applies prospecting when
    it rolls a drop, so a recorded observation is ALREADY the post-bonus rate.
    Using a learned rate AND `_prospecting_relief` would count the bonus twice —
    so the relief applies only on the static fallback, where nothing has been
    observed and the bonus is therefore absent from the number.

    That is also why the learned branch needs no prospecting argument of its own:
    the character whose cycles were recorded is the character being priced, and
    its gear is baked in. A different character's rate would not be transferable
    for exactly the same reason.

    Measured 2026-08-08 over 4,000+ kills: the static table is accurate to ~3% on
    large samples, so this mostly CONFIRMS it. The exceptions are the ones worth
    having — `chicken/feather` 14.8% observed vs 12.5% static, `sheep/wool` 11.8%
    vs 8.3% — both saying a drop route is cheaper than it was being priced."""
    observed = (store.observed_drop_rate(monster_code, item)
                if store is not None else None)
    if observed is not None and observed > 0:
        return 1 / Fraction(observed).limit_denominator(10 ** 6)
    return expected_kills(MonsterDropCandidate(
        monster_code=monster_code, rate=rate, min_quantity=min_q,
        max_quantity=max_q, distance=0)) * _prospecting_relief(prospecting)


def _drop_actions(item: str, monster_code: str, rate: int, min_q: int, max_q: int,
                  state: WorldState, game_data: GameData,
                  store: LearningStore | None) -> int:
    """Whole-loop actions to farm ONE unit off `monster_code`.

    Two proved pieces, multiplied, and neither is restated here:
    `expected_kills` (`rate / avg_yield`, exact `Fraction`, proved in
    `Formal.MonsterDropSelection`) times `cycles_per_kill` — the SAME
    fight-plus-forced-rest figure `cheapest_path_to_level` spends, so a drop farm
    and a level grind are quoted in identical units. Using a bare kill count here
    would price the farm at roughly half its real cost, which is the defect
    `fight_loop_cost` was written to fix.

    Rounded UP: a fractional action is still an action the character spends, and
    the objective is an exact integer (S-013)."""
    projected = project_loadout_stats(
        state, pick_loadout_cached(Rank(), state, game_data), game_data)
    kills = _expected_kills_per_unit(item, monster_code, rate, min_q, max_q,
                                     projected.prospecting, store)
    per_kill = cycles_per_kill(
        expected_damage_per_fight(state, game_data, monster_code), state.max_hp)
    return max(1, ceil(float(kills) * per_kill))


def _priced(item: str, source: Source, state: WorldState,
            game_data: GameData,
            store: LearningStore | None = None) -> RouteOption:
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
                           actions_per_application=1,
                           yield_per=max(1, game_data.max_gather_yield),
                           capacity=source.capacity)
    if source.kind is SourceKind.BUY:
        price, currency = _price_of(item, source.code, game_data)
        return RouteOption(kind=source.kind.value, venue=source.code,
                           actions_per_application=1, yield_per=source.yield_per,
                           capacity=source.capacity, inputs={currency: price})
    rate, min_q, max_q = _drop_table(item, source.code, game_data)
    return RouteOption(
        kind=source.kind.value, venue=source.code,
        actions_per_application=_drop_actions(item, source.code, rate, min_q,
                                              max_q, state, game_data, store),
        yield_per=source.yield_per, capacity=source.capacity)


def _price_of(item: str, npc_code: str, game_data: GameData) -> tuple[int, str]:
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


def _drop_table(item: str, monster_code: str,
                game_data: GameData) -> tuple[int, int, int]:
    """`(rate, min_quantity, max_quantity)` for this monster's drop of `item`.
    Same contract as `_price_of`: the row exists because `obtain_sources` built
    the DROP source from it."""
    for code, rate, min_q, max_q in game_data.monsters_dropping(item):
        if code == monster_code:
            return rate, min_q, max_q
    raise KeyError(f"no {monster_code} drop row for {item}")


def _gated_craft_option(item: str, state: WorldState, game_data: GameData,
                        store: LearningStore) -> RouteOption | None:
    """The CRAFT route `obtain_sources` withholds because the skill gate is
    unmet — priced with the grind that would open it.

    THE SEAM, STATED OUT LOUD. `obtain_sources` answers READINESS: what can the
    executor serve *right now*. A skill-gated craft genuinely cannot be served
    right now, so excluding it there is correct. This module answers a different
    question — what would it COST to obtain this — and that answer may include
    making a route ready. The gate is a price, not a wall.

    That distinction is real, but it is also how a second route model creeps
    back in, which is the thing this epic exists to kill. So this is the ONLY
    route this module may add that `obtain_sources` did not name, and a census
    pins that (`test_the_pricer_adds_nothing_but_gated_crafts`).

    `None` — no route at all — only when a grind could not open the craft anyway:

      * the item is not craftable, or names no crafting skill;
      * the gate is already MET (then `obtain_sources` names the craft itself,
        and adding a second copy would double the route);
      * no workshop is known (a grind cannot conjure a bench, so paying it would
        buy nothing).

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

    So: no observations, a non-positive observed rate, or no `<skill>_max_xp`
    from the API all decline the route. A non-positive rate is EVIDENCE the grind
    is not progressing, which is a stronger reason to decline than ignorance is.
    Declining costs the character that one route, not its progress — every other
    root still competes."""
    recipe = game_data.crafting_recipe(item)
    stats = game_data.item_stats(item)
    if recipe is None or stats is None or not stats.crafting_skill:
        return None
    skill = stats.crafting_skill
    if state.skills.get(skill, 1) >= stats.crafting_level:
        return None
    if game_data.workshop_location(skill) is None:
        return None
    rate = store.skill_xp_per_cycle_all(skill)
    max_xp = state.skill_max_xp.get(skill, 0)
    if not rate or rate <= 0 or max_xp <= 0:
        return None
    grind = skill_grind_cycles(
        state.skills.get(skill, 1), state.skill_xp.get(skill, 0),
        max_xp, stats.crafting_level, rate)
    return RouteOption(
        kind=SourceKind.CRAFT.value, venue=_workshop_venue(skill),
        actions_per_application=1, yield_per=game_data.craft_yield(item),
        capacity=UNBOUNDED_CAPACITY, inputs=dict(recipe),
        unlock=f"skill:{skill}:{stats.crafting_level}",
        unlock_actions=grind,
    )


def route_options(item: str, state: WorldState, game_data: GameData,
                  ctx: SelectionContext,
                  store: LearningStore | None = None) -> list[RouteOption]:
    """Every route to `item`, priced: the ones `obtain_sources` names, plus —
    only when a `store` is supplied — the skill-gated craft it withholds.

    `store` defaults to None so every existing caller keeps today's behaviour
    exactly. A gated craft cannot be priced without an observed grind rate, and
    the store is the only thing that has one."""
    routes = [_priced(item, s, state, game_data, store)
              for s in obtain_sources(item, state, game_data, ctx)]
    if store is not None:
        gated = _gated_craft_option(item, state, game_data, store)
        if gated is not None:
            routes.append(gated)
    return routes


def acquisition_options(item: str, state: WorldState, game_data: GameData,
                        ctx: SelectionContext,
                        store: LearningStore | None = None
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
    PRICE it; this only has to enumerate."""
    options: dict[str, list[RouteOption]] = {}
    frontier = [item]
    while frontier:
        code = frontier.pop()
        if code in options:
            continue
        routes = route_options(code, state, game_data, ctx, store)
        options[code] = routes
        for route in routes:
            frontier.extend(route.inputs)
    return options


def acquisition_actions(item: str, qty: int, state: WorldState,
                        game_data: GameData, ctx: SelectionContext,
                        equip: bool,
                        store: LearningStore | None = None) -> int:
    """Lower bound on planner actions to obtain (and optionally equip) `qty` of
    `item`, over every route the executor can currently serve.

    Drop-in shape for `min_plan_length`'s call sites, with `state`/`ctx` added
    because routes are STATE-AWARE — which is the whole point, and also the
    reason `acquisition_cost_core.UNOBTAINABLE_PER_UNIT` must never be cached
    across cycles.

    HOLDINGS ARE THE BAG ONLY, AND THAT IS A CHANGE. `min_plan_length`'s callers
    pass inventory PLUS bank (`branch_objective._held`), because that model has
    no withdraw action and so must treat a banked copy as already in hand. Here
    the bank is a ROUTE — `SourceKind.WITHDRAW`, capacity = the bank's stock —
    so counting it as owned too would credit the same copy twice and price the
    trip to the bank at nothing. A banked item costs one hop plus one withdraw,
    which is what it costs."""
    owned: dict[str, int] = dict(state.inventory)
    options: Mapping[str, list[RouteOption]] = acquisition_options(
        item, state, game_data, ctx, store)
    return acquisition_cost(item, qty, options, owned) + (
        EQUIP_ACTIONS if equip else 0)


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
    owned: dict[str, int] = dict(state.inventory)
    options: dict[str, list[RouteOption]] = {}
    for item, _qty in roots:
        options.update(acquisition_options(item, state, game_data, ctx, store))
    total, paid = bundle_acquisition_cost(roots, options, owned)
    return total + (EQUIP_ACTIONS * len(roots) if equip else 0), paid

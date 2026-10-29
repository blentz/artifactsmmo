"""ObtainModel: every route to every item, with every gate evaluated.

Phase 1 of `docs/PLAN_decision_architecture_redesign.md`. One model replaces the
seventeen that each answered "can I get X / how" with a different subset of the
real gates. It enumerates ALL routes, evaluates ALL gates on each, and leaves
the choice of which gates count to an explicit `Policy`.

`obtain_sources` is a view of this model under `Policy.LEGACY` (Phase 1 step 3).
Before that switch, a census compared the two over every item of real game data
(44 scenario worlds with the bank open and locked, and all five live characters):
zero differences.

PRIORITY ORDER. `routes` lists routes in the declared order WITHDRAW, RECYCLE,
CRAFT, GATHER, BUY, GE_FILL, DROP, TASK_REWARD, GOLD_DROP, SELL: routes that consume stock already owned
before routes that create new work, and GE_FILL (finite, may be taken first)
directly below BUY at the same gold cost.

ELIGIBILITY MIRRORS THE ACTION POOL, NOT MERELY WHAT `is_applicable` WOULD SAY
IF ASKED. A route the executor cannot actually serve is a leaf with no plan (the
livelock shape of `3166d390`), so each existence test and gate below matches the
condition under which `actions/factory.py` builds, and the action accepts, the
action that serves it. The per-kind reasons are on each `_<kind>` method.

Built once per decision from one `(state, game_data, ctx, now)` snapshot, and
memoised per item for its lifetime. Pure: no I/O.
"""

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from fractions import Fraction

from artifactsmmo_cli.ai import accumulation_sell
from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.decompose_core import Route as WalkRoute
from artifactsmmo_cli.ai.decompose_core import can_obtain, next_step, plan_legs
from artifactsmmo_cli.ai.event_availability import event_npc_tradeable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_selection import GatherCandidate, rank_gather_sources
from artifactsmmo_cli.ai.inventory_keep import destroyable
from artifactsmmo_cli.ai.obtain_model.drop_routes import Fighter, drop_routes, gold_drop_routes
from artifactsmmo_cli.ai.obtain_model.gate import Door, Gate, GateKind
from artifactsmmo_cli.ai.obtain_model.policy import Policy
from artifactsmmo_cli.ai.obtain_model.ready_core import ready_routes
from artifactsmmo_cli.ai.obtain_model.route import UNBOUNDED_CAPACITY, Route
from artifactsmmo_cli.ai.obtain_model.walk_graph import WalkAnswer, WalkGraph
from artifactsmmo_cli.ai.region_edges import (
    content_reached,
    door_legs,
    doors_to,
    leg_states,
    reachable_regions_now,
)
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.world_state import GOLD_CODE, WorldState

_MINTS = (SourceKind.CRAFT, SourceKind.GATHER, SourceKind.BUY, SourceKind.DROP,
          SourceKind.TASK_REWARD, SourceKind.GOLD_DROP)
"""Route kinds that make new copies, as opposed to moving existing ones."""

DEFAULT_SKILL_LEVEL = 1
"""A skill absent from `state.skills` is at the API's starting level (D-Q)."""


class ObtainModel:
    """All routes to any item from one snapshot of the world.

    `fighter`, when given, is the character a DROP route's WINNABLE gate is
    asked of (at full hp) instead of `state`: a projected loadout (the global
    gear objective's fixed point, spec 2026-10-18 §2.3), or a function giving
    that character per dropping monster (each monster judged on its own target
    loadout). It is never stock: the bag, bank and pocket are always
    `state`'s.

    `crossing`, when given, is the state the crossings are asked of (every
    SPAWN_KNOWN gate's reach and doors): the real state of a walk whose
    `state` pocket is only the gold its buys may spend
    (`progression_reserve.spendable_pocket`). A fee is reserve-guarded at the
    crossing itself (ruling T14e-2), so asking it of the spendable pocket would
    keep the reserve twice. A door's shortfall is gold to EARN, the same on
    either pocket."""

    def __init__(self, state: WorldState, game_data: GameData,
                 ctx: SelectionContext, now: datetime,
                 fighter: Fighter | None = None, crossing: WorldState | None = None) -> None:
        self._state = state
        self._crossing = state if crossing is None else crossing
        self._fighter = fighter
        self._gd = game_data
        self._ctx = ctx
        self._now = now
        self._routes: dict[str, tuple[Route, ...]] = {}
        self._regions: frozenset[str] | None = None
        self._doors: dict[tuple[object, ...], bool] = {}

    def _reach(self) -> frozenset[str]:
        """The regions the walk reaches from this state now
        (`region_edges.reachable_regions_now`), walked once per model."""
        if self._regions is None:
            self._regions = reachable_regions_now(self._crossing, self._gd)
        return self._regions

    def routes(self, item: str) -> tuple[Route, ...]:
        """Every route to `item` in priority order, usable or not."""
        cached = self._routes.get(item)
        if cached is None:
            cached = (*self._withdraw(item), *self._recycle(item), *self._craft(item),
                      *self._gather(item), *self._buy(item), *self._ge_fill(item),
                      *self._drop(item), *self._task_reward(item), *self._gold_drop(item),
                      *self._sell(item))
            self._routes[item] = cached
        return cached

    def mints(self, item: str) -> bool:
        """Does anything make new copies of `item`, readiness ignored? A route
        that creates (CRAFT, GATHER, BUY, DROP, TASK_REWARD, GOLD_DROP), whatever its gates
        say today. WITHDRAW, RECYCLE and GE_FILL only move copies that already
        exist, so an item with no other route is fixed supply: every copy there
        will ever be exists now. SELL is left out with them: it exists only
        while a licensed surplus does, so it is stock, not a capability."""
        return any(route.kind in _MINTS for route in self.routes(item))

    def ready(self, item: str, policy: Policy) -> tuple[Route, ...]:
        """The routes to `item` usable right now under `policy`, in priority
        order (see `ready_core.ready_routes`, the proved selection)."""
        return ready_routes(self.routes(item), policy)

    def gated_by(self, item: str, policy: Policy, kind: GateKind) -> tuple[Route, ...]:
        """The routes to `item` that `policy` offers and that ONE kind of gate
        alone keeps from being ready: every enforced gate it does not satisfy is
        of `kind`. A price-aware caller can pay for that gate (a skill grind for
        CRAFT_SKILL, a gear chain for WINNABLE) instead of treating the route as
        a wall; a route also blocked by anything else is still a wall."""
        return tuple(
            route for route in self.routes(item)
            if policy.admits(route)
            and (unmet := {gate.kind for gate in route.gates
                           if policy.enforces(gate, route) and not gate.satisfied})
            and unmet == {kind})

    def past_a_door(self, item: str, policy: Policy,
                    companions: frozenset[GateKind]) -> tuple[tuple[Route, tuple[Gate, ...]], ...]:
        """The routes to `item` that `policy` offers whose content stands past
        a door (Task 14e): an unmet SPAWN_KNOWN gate naming doors, and every
        other unmet enforced gate of a kind in `companions` (the gates a
        price-aware caller can pay for alongside the door). Each with its unmet
        gates, in route order."""
        out: list[tuple[Route, tuple[Gate, ...]]] = []
        for route in self.routes(item):
            if not policy.admits(route):
                continue
            unmet = tuple(gate for gate in route.gates
                          if policy.enforces(gate, route) and not gate.satisfied)
            if (any(gate.kind is GateKind.SPAWN_KNOWN and gate.doors for gate in unmet)
                    and all(gate.kind is GateKind.SPAWN_KNOWN or gate.kind in companions
                            for gate in unmet)):
                out.append((route, unmet))
        return tuple(out)

    def feasible(self, item: str, qty: int, policy: Policy,
                 produce: frozenset[str] = frozenset(),
                 keep: frozenset[str] = frozenset()) -> bool:
        """Can `qty` units of `item` be obtained from here under `policy`?

        The one walk's answer (`decompose_core.can_obtain` over `walk_graph`,
        `Decompose.feasible`): the bag, banked copies withdrawn, and the ready
        routes of the closure filled jointly, so two inputs that draw on the
        same stock share it and stock and production mix. The same call
        decomposition makes, so "can I" and "what next" cannot disagree (Phase
        2d-F). `produce` and `keep` are `walk_graph`'s: an item that must be
        MADE, and items no recycle or sale may destroy."""
        graph = self.walk_graph(item, policy, produce, keep=keep)
        return can_obtain(item, qty, graph.on_hand, graph.routes)

    def in_bag(self, item: str) -> int:
        """Units of `item` in the bag, the walk's on hand (gold: the pocket)."""
        return self._state.gold if item == GOLD_CODE else self._state.inventory.get(item, 0)

    def walk_graph(self, item: str, policy: Policy,
                   produce: frozenset[str] = frozenset(),
                   openable: Callable[[Gate], bool] = lambda _gate: False,
                   keep: frozenset[str] = frozenset(),
                   grey_ok: Callable[[str], bool] = lambda _item: False,
                   opening: frozenset[Door] = frozenset(),
                   prefer: Callable[[str], tuple[SourceKind, str] | None] = lambda _item: None,
                   rank: Callable[[Door], int] = lambda _door: 0) -> WalkGraph:
        """`item`'s closure as the one walk's graph (Phase 2c-2b).

        On hand is the bag (the inventory, with gold as the pocket). Every ready
        route under `policy` is a walk route, in priority order, the walk's
        greedy fill mixing them: a WITHDRAW route's capacity is the bank's
        stock, so banked copies are withdrawn and the rest produced. A RECYCLE
        or SELL route consumes one copy of the item it destroys or sells per
        application, so that copy is its input (a banked copy is withdrawn
        first), and its capacity is capped at the copies held, so the walk never
        makes a copy in order to destroy it.

        `produce` names items the goal must MAKE, not merely hold: a skill
        grind's rung, whose XP is in the craft (or the gather). Only their
        CRAFT and GATHER routes are kept, wherever they occur: withdrawing a
        banked rung would satisfy the count and earn nothing (the held-rung
        livelock), and so would buying one, filling it on the GE or taking it
        as a drop (Phase 2d-L3: the grind now asks for the rung itself).
        `keep` names items no RECYCLE or SELL may destroy as a
        source: the goal's own target (recycling a held copper_ring for the bar
        to craft a copper_ring is a null cycle) and every `produce` item.

        `openable` says which unmet gates an action can open (a skill gate a
        grind can raise). A route `policy` offers whose every unmet enforced
        gate is openable joins the walk AFTER the ready routes, carrying those
        gates: the walk then opens them first, as a sub-task, and only when
        nothing ready serves (Phase 2c-2c).

        `grey_ok` names items whose ZERO-XP droppers count even though `policy`
        refuses grey (`allow_grey=False`): the walk applies the grey-farm
        directive per item, as the search's admission did (a skill grind, a
        drop the directive allows, an upgrade's own target).

        A KEY DOOR IS A ROUTE THROUGH ITS KEY (Task 14e, M-3). A fight or a
        gather whose SPAWN_KNOWN gate is unmet because its content stands past
        a door (`Gate.doors`) joins the walk the same way, carrying that gate
        narrowed to the first door whose shortfall the walk can obtain
        (`_door_open`): the walk then opens it first, as a sub-task (obtain
        the key or the fee; the crossing follows in the plan's region bridge).
        The door is opened for every caller, `openable` or not: obtaining an
        item is not a grind, and `feasible` must count what the walk serves.
        `opening` holds the doors whose keys are being walked further up, so a
        key that stands only past its own door is a wall, not a loop.

        `prefer` names, per item with a route past a door, the `(kind, via)`
        route the pricer took for it (`acquisition_cost.door_route`, ruling
        T14e-1): that route is tried first, so a door route priced below a
        ready one is the one the walk serves. None leaves the order alone.

        `rank` prices a door (`acquisition_cost.door_price`, ruling T14e-m1):
        of the doors the walk can open, the gate is narrowed to the cheapest,
        first of equal ranks, the door the pricer charged. The default ranks
        every door alike, so the first openable one in `door_reaches`' order."""
        bag: dict[str, int] = dict(self._state.inventory)
        bag[GOLD_CODE] = self._state.gold
        bank = self._state.bank_items or {}
        routes: dict[str, tuple[WalkRoute[str], ...]] = {}
        sources: dict[str, tuple[Route, ...]] = {}
        pending = [item]
        while pending:
            code = pending.pop()
            if code in routes:
                continue
            walk: list[WalkRoute[str]] = []
            behind: list[Route] = []
            item_policy = (replace(policy, allow_grey=True)
                           if not policy.allow_grey and grey_ok(code) else policy)
            ready = self.ready(code, item_policy)
            gated: list[tuple[Route, tuple[Gate, ...]]] = []
            for route in self.routes(code):
                if not item_policy.admits(route) or route in ready:
                    continue
                unmet = tuple(gate for gate in route.gates
                              if item_policy.enforces(gate, route) and not gate.satisfied)
                if not unmet or not all(openable(gate) or gate.doors for gate in unmet):
                    continue
                opened = [self._opened(gate, policy, openable, keep, grey_ok, opening, rank)
                          for gate in unmet]
                if all(gate is not None for gate in opened):
                    gated.append((route, tuple(gate for gate in opened if gate is not None)))
            candidates = [(route, ()) for route in self._ranked_gathers(code, ready)] + gated
            if gated and any(gate.doors for _route, gates in gated for gate in gates):
                first = prefer(code)
                candidates.sort(key=lambda pair: (pair[0].kind, pair[0].via) != first)
            for route, gates in candidates:
                if code in produce and route.kind not in (SourceKind.CRAFT, SourceKind.GATHER):
                    continue
                if route.kind in (SourceKind.RECYCLE, SourceKind.SELL) and route.via in (keep | produce):
                    continue
                inputs = tuple(route.inputs.items())
                capacity = route.capacity
                if route.kind in (SourceKind.RECYCLE, SourceKind.SELL):
                    inputs = ((route.via, 1),)
                    copies = bag.get(route.via, 0) + bank.get(route.via, 0)
                    capacity = min(capacity, copies * route.yield_per)
                walk.append(WalkRoute(len(walk), route.yield_per, capacity, inputs, gates))
                behind.append(route)
            routes[code] = tuple(walk)
            sources[code] = tuple(behind)
            pending.extend(x for w in walk for x, _per in w.inputs)
        return WalkGraph(bag, routes, sources)

    def door_open(self, door: Door, policy: Policy) -> bool:
        """Can the walk obtain `door`'s shortfall under `policy`, with no
        caller gate opened (`_door_open`)? The verdict a census reads to
        agree with the walk on which doors it routes through."""
        return self._door_open(door, policy, lambda _gate: False, frozenset(),
                               lambda _item: False, frozenset({door}), lambda _door: 0)

    def _opened(self, gate: Gate, policy: Policy, openable: Callable[[Gate], bool],
                keep: frozenset[str], grey_ok: Callable[[str], bool],
                opening: frozenset[Door], rank: Callable[[Door], int]) -> Gate | None:
        """`gate` as the walk opens it, or None when nothing opens it: the
        caller's `openable` gate itself, or a door gate narrowed to the
        cheapest (`rank`, first of equal ranks) of its doors not already being
        opened whose shortfall the walk can obtain. The doors are tried
        cheapest first and the first that opens is taken, so no door dearer than
        it is walked (ruling T14e-perf: a key's walk is the cost of a door)."""
        if openable(gate):
            return gate
        door = next((door for door in sorted(gate.doors, key=rank) if door not in opening
                     and self._door_open(door, policy, openable, keep, grey_ok, opening | {door},
                                         rank)),
                    None)
        return None if door is None else replace(gate, doors=(door,))

    def _door_open(self, door: Door, policy: Policy, openable: Callable[[Gate], bool],
                   keep: frozenset[str], grey_ok: Callable[[str], bool],
                   opening: frozenset[Door], rank: Callable[[Door], int]) -> bool:
        """Can the walk obtain `door`'s whole shortfall on top of the bag: each
        key (or the fee's gold) asked of the one walk on its own closure, with
        `opening` closed to it. Memoised for the model's lifetime: the key
        holds the callables themselves, so an entry pins what it was asked
        with and no other callable can share its answer."""
        key = (door, policy, keep, opening, openable, grey_ok, rank)
        if key not in self._doors:
            legs = door_legs(door, self._crossing, self._gd)
            closed = opening | set(legs)
            self._doors[key] = all(
                can_obtain(code, model.in_bag(code) + units, graph.on_hand, graph.routes)
                for leg, model in zip(legs, self._leg_models(door), strict=True)
                for code, units in leg
                for graph in (model.walk_graph(code, policy, keep=keep, openable=openable,
                                               grey_ok=grey_ok, opening=closed, rank=rank),))
        return self._doors[key]

    def _leg_models(self, door: Door) -> list["ObtainModel"]:
        """One model per leg of a door chain (ruling T14e-m6): this one for
        the first leg, then one per later leg over `region_edges.leg_states`:
        its crossings asked of the state holding the legs before it (they are
        crossed from here), its pocket and bag past them, their tolls paid
        (round 4: an earlier leg's fee gold is spent, not credited)."""
        return [self, *(ObtainModel(at, self._gd, self._ctx, self._now, self._fighter,
                                    crossing=cross)
                        for at, cross in leg_states(self._state, self._crossing, door,
                                                    self._gd)[1:])]

    def _ranked_gathers(self, item: str, ready: tuple[Route, ...]) -> list[Route]:
        """`ready` with its GATHER routes (contiguous in priority order) ranked
        by the proved gather-source order (`gather_selection`, expected gathers
        per unit at the context's learned drop chance, then distance to the
        nearest tile, then code), so the walk's first gather is the one
        `select_gather_source` picks; every other route keeps its place.

        The expected gathers are the context's drop evidence
        (`SelectionContext.drops`, ruling T16a) over the drop row
        (`GameData.gather_drop_row`, a primary-map-only resource a sure drop),
        at `state.prospecting`: the figure the walk prices the route at, so
        the source the walk serves first is the one it priced cheapest."""
        gathers = [route for route in ready if route.kind is SourceKind.GATHER]
        if len(gathers) < 2:
            return list(ready)
        evidence = self._ctx.drops()
        candidates: list[GatherCandidate] = []
        for route in gathers:
            rate, min_q, max_q = self._gd.gather_drop_row(route.via, item)
            attempts = evidence.attempts_per_unit(route.via, item, rate, min_q, max_q,
                                                  self._state.prospecting)
            tiles = self._gd.all_resource_locations.get(route.via) or []
            distance = min((abs(x - self._state.x) + abs(y - self._state.y) for x, y in tiles), default=0)
            candidates.append(GatherCandidate(route.via, attempts, distance))
        by_resource = {route.via: route for route in gathers}
        ranked = iter([by_resource[code] for code in rank_gather_sources(candidates)])
        return [next(ranked) if route.kind is SourceKind.GATHER else route for route in ready]

    def walk(self, item: str, qty: int, policy: Policy,
             produce: frozenset[str] = frozenset(),
             openable: Callable[[Gate], bool] = lambda _gate: False,
             keep: frozenset[str] = frozenset(),
             grey_ok: Callable[[str], bool] = lambda _item: False,
             prefer: Callable[[str], tuple[SourceKind, str] | None] = lambda _item: None,
             rank: Callable[[Door], int] = lambda _door: 0) -> WalkAnswer:
        """The one walk over `item`'s closure: can `qty` be had, and the next
        step toward it (`decompose_core`)."""
        graph = self.walk_graph(item, policy, produce, openable, keep, grey_ok, prefer=prefer,
                                rank=rank)
        return WalkAnswer(can_obtain(item, qty, graph.on_hand, graph.routes),
                          next_step(item, qty, graph.on_hand, graph.routes), graph,
                          tuple(plan_legs(item, qty, graph.on_hand, graph.routes)))

    def _skill(self, skill: str) -> int:
        return self._state.skills.get(skill, DEFAULT_SKILL_LEVEL)

    def _withdraw(self, item: str) -> list[Route]:
        """A copy sits in the bank. Gated on `ctx.bank_accessible`: that is a
        persisted, level-gated blocker that stays False for the whole early game
        while `state.bank_items` is populated regardless, and
        `WithdrawItemAction.is_applicable` refuses unconditionally without it."""
        stock = (self._state.bank_items or {}).get(item, 0)
        if stock <= 0:
            return []
        gate = Gate(GateKind.BANK_ACCESSIBLE, "bank", self._ctx.bank_accessible)
        return [Route(item, SourceKind.WITHDRAW, item, 1, stock, (gate,))]

    def _recycle(self, item: str) -> list[Route]:
        """Held (bag or bank) equippables whose recipe consumes `item`.

        A non-equippable has no RecycleAction in existence (`factory.py` builds
        them only for equippable codes), so it is no route at all rather than a
        gated one. The yield is the LEARNED expectation per unit recycled
        (`GameData.recycle_unit_yield`: the item's observed per-unit total,
        split at random across the recipe); an item never recycled, or one
        whose expected share of `item` is under one unit, is no route.
        `LICENSED` asks the keep authority (`destroyable`) for
        copies it may destroy, never raw stock, which would license melting
        protected copies.

        `GameData.recipe_consumers` inverts the question ("which recipes consume
        `item`?"), so holdings enter as an O(1) membership test. Scanning every
        held code instead was 94% of a large search (profiled 2026-08-13)."""
        out: list[Route] = []
        bank = self._state.bank_items or {}
        for code in self._gd.recipe_consumers.get(item, ()):
            if code not in self._state.inventory and code not in bank:
                continue
            recipe = self._gd.crafting_recipe(code)
            assert recipe is not None and item in recipe, (
                f"recipe_consumers[{item!r}] lists {code!r}, whose recipe is {recipe!r}")
            stats = self._gd.item_stats(code)
            if stats is None or not stats.crafting_skill or not ITEM_TYPE_TO_SLOTS.get(stats.type_):
                continue
            unit_yield = self._gd.recycle_unit_yield(code)
            yield_per = unit_yield.get(item, 0) if unit_yield is not None else 0
            if yield_per == 0:
                continue
            copies = destroyable(code, self._state, self._gd, self._ctx)
            gates = (
                Gate(GateKind.CRAFT_SKILL, stats.crafting_skill,
                     self._skill(stats.crafting_skill) >= stats.crafting_level,
                     stats.crafting_level),
                Gate(GateKind.WORKSHOP_KNOWN, stats.crafting_skill,
                     self._gd.workshop_location(stats.crafting_skill) is not None),
                Gate(GateKind.LICENSED, code, copies > 0),
            )
            out.append(Route(item, SourceKind.RECYCLE, code, yield_per,
                             max(copies, 0) * yield_per, gates))
        return out

    def _craft(self, item: str) -> list[Route]:
        """`item` has a recipe; gated on the crafting skill and on a known
        workshop (a recipe with no workshop on file cannot be executed)."""
        recipe = self._gd.crafting_recipe(item)
        if recipe is None:
            return []
        stats = self._gd.item_stats(item)
        if stats is None or not stats.crafting_skill:
            return []
        gates = (
            Gate(GateKind.CRAFT_SKILL, stats.crafting_skill,
                 self._skill(stats.crafting_skill) >= stats.crafting_level,
                 stats.crafting_level),
            Gate(GateKind.WORKSHOP_KNOWN, stats.crafting_skill,
                 self._gd.workshop_location(stats.crafting_skill) is not None),
        )
        return [Route(item, SourceKind.CRAFT, item, self._gd.craft_yield(item),
                      UNBOUNDED_CAPACITY, gates, inputs=dict(recipe))]

    def _gather(self, item: str) -> list[Route]:
        """One route per resource that drops `item`, fewest expected gathers a
        unit first: the context's learned drop model
        (`SelectionContext.drops`, ruling T16a) over each drop row at
        `state.prospecting`, the figure the walk prices the route at. The first
        one is marked `primary`: the only one the legacy model offers, so a
        LEGACY walk prices the source the evidence says is cheapest, not the
        one the API rate alone names. Under the prior (`LearnedDrops.empty()`)
        that is the minimal `rate / mean quantity` dropper; the stable sort
        keeps table order on a tie. A resource known only from the
        primary-drop map is a sure drop (`GameData.gather_drop_row`)."""
        droppers = [res for res, table in self._gd.resource_drops_full.items()
                    for code, _rate, _mn, _mx in table if code == item]
        if not droppers:
            droppers = [res for res, code in self._gd.resource_drops.items() if code == item]
        evidence = self._ctx.drops()

        def attempts(resource: str) -> Fraction:
            rate, min_q, max_q = self._gd.gather_drop_row(resource, item)
            return evidence.attempts_per_unit(resource, item, rate, min_q, max_q,
                                              self._state.prospecting)

        out: list[Route] = []
        for rank, resource in enumerate(sorted(droppers, key=attempts)):
            # SPAWN_KNOWN is the walk's reach alone (ruling I-3, as T14a-E for
            # a fight, with the same guard: ruling R3-M1): a resource whose
            # every tile stands past a crossing the character cannot pay for
            # now is no route. `resource_spawn_known` is not asked as well. The
            # two agree whenever the state's region is one the catalogue's
            # fixed point reaches; the fixed point starts from the overworld,
            # so in a pocket entered through an edge it does not model it
            # would refuse a gather the character can make where it stands.
            tiles = self._gd.all_resource_locations.get(resource, [])
            known = content_reached(resource, tiles, self._gd, self._reach())
            doors = () if known else doors_to(resource, tiles, self._crossing, self._gd)
            gates = [Gate(GateKind.SPAWN_LIVE, resource, bool(tiles)),
                     Gate(GateKind.SPAWN_KNOWN, resource, known, doors=doors)]
            requirement = self._gd.resource_skill_level(resource)
            if requirement is not None:
                skill, level = requirement
                gates.append(Gate(GateKind.GATHER_SKILL, skill, self._skill(skill) >= level, level))
            out.append(Route(item, SourceKind.GATHER, resource, 1, UNBOUNDED_CAPACITY,
                             tuple(gates), primary=rank == 0))
        return out

    def _buy(self, item: str) -> list[Route]:
        """Every vendor selling `item`. `VENDOR_PERMANENT` is what the legacy
        model required (an event vendor was not reliably reachable, so could not
        anchor a plan); `VENDOR_TRADEABLE` is the finer question the
        `event_vendors` policy asks instead (D-F)."""
        out: list[Route] = []
        for npc, price, currency in self._gd.npc_purchases(item):
            gates = (
                Gate(GateKind.VENDOR_PERMANENT, npc, not self._gd.is_event_npc(npc)),
                Gate(GateKind.VENDOR_LOCATED, npc, self._gd.npc_location(npc) is not None),
                Gate(GateKind.VENDOR_TRADEABLE, npc, self._tradeable(npc)),
            )
            out.append(Route(item, SourceKind.BUY, npc, 1, UNBOUNDED_CAPACITY, gates,
                             inputs={currency: price}))
        return out

    def _ge_fill(self, item: str) -> list[Route]:
        """A STANDING Grand Exchange sell order for `item`: route EXISTENCE, not
        venue choice. Whether the GE beats the NPC price is decided downstream on
        the priced options; applying that test here left an item sold ONLY on the
        GE with no route at all. A merely postable order may never fill, so it
        is not a route. Capacity is the order's quantity, and no `is_event_npc`
        gate applies: the Grand Exchange is not an NPC."""
        order = self._gd.ge_best_sell_order(item)
        if order is None:
            return []
        order_id, price, quantity = order
        gate = Gate(GateKind.GE_LOCATED, "grand_exchange",
                    self._gd.grand_exchange_location() is not None)
        return [Route(item, SourceKind.GE_FILL, order_id, 1, quantity, (gate,),
                      inputs={GOLD_CODE: price})]

    def _drop(self, item: str) -> list[Route]:
        """Monsters that drop `item`: see `drop_routes`, the one place drop gates
        are evaluated (shared with `drop_obtainability`), judged against the
        projected `fighter` when one is given."""
        return drop_routes(item, self._state, self._gd, self._crossing, self._fighter)

    def _task_reward(self, item: str) -> list[Route]:
        """The task board pays `item`: one application is a whole task loop
        (accept, do, turn in). No gate: the loop runs from any state
        (`ReachCurrencyGoal` plans it), which is why `is_attainable_now` always
        counted a task-earned currency. `yield_per` is 1, the least any award
        pays (the loader enforces >= 1 for coins): with no inputs and no
        capacity limit, the yield cannot change a feasibility answer, and a cost
        reads the task tables' real amounts itself."""
        if not self._gd.is_task_earnable(item):
            return []
        return [Route(item, SourceKind.TASK_REWARD, "tasks", 1, UNBOUNDED_CAPACITY, ())]

    def _gold_drop(self, item: str) -> list[Route]:
        """GOLD only: the gold a won fight pays, one route per paying monster
        (see `drop_routes.gold_drop_routes`, which shares the fight gates)."""
        if item != GOLD_CODE:
            return []
        return gold_drop_routes(self._state, self._gd, self._crossing)

    def _sell(self, item: str) -> list[Route]:
        """GOLD only: selling what the keep authority licenses, one route per
        (item sold, buyer), buyers highest price first.

        Gold is an INPUT (a gold-priced vendor route carries `{"gold": price}`),
        so without a way to obtain it a 430-gold shortfall priced at 430 million
        actions. The licence is `accumulation_sell.sellable_surplus`, the same
        authority the SELL_IDLE means asks, so the route never prices a sale the
        means would refuse. Reachability is `event_npc_tradeable`, not the blunt
        `is_event_npc` refusal BUY uses: every NPC in the game that buys items
        is an event NPC (55 of 55 buyer rows)."""
        if item != GOLD_CODE:
            return []
        out: list[Route] = []
        surplus = accumulation_sell.sellable_surplus(self._state, self._gd, self._ctx)
        for code, copies in sorted(surplus.items()):
            for npc, price in self._gd.npcs_buying_item(code):
                if price <= 0:
                    continue
                gates = (
                    Gate(GateKind.VENDOR_LOCATED, npc, self._gd.npc_location(npc) is not None),
                    Gate(GateKind.VENDOR_TRADEABLE, npc, self._tradeable(npc)),
                )
                out.append(Route(item, SourceKind.SELL, code, price, copies * price, gates,
                                 agent=npc))
        return out

    def _tradeable(self, npc: str) -> bool:
        return event_npc_tradeable(npc, self._gd, x=self._state.x, y=self._state.y,
                                   active_events=self._state.active_events, now=self._now)

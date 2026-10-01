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
from datetime import datetime

from artifactsmmo_cli.ai import accumulation_sell
from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.decompose_core import Route as WalkRoute
from artifactsmmo_cli.ai.decompose_core import can_obtain, next_step, plan_legs
from artifactsmmo_cli.ai.event_availability import event_npc_tradeable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_selection import GatherCandidate, rank_gather_sources
from artifactsmmo_cli.ai.inventory_keep import destroyable
from artifactsmmo_cli.ai.obtain_model.drop_routes import drop_routes, gold_drop_routes
from artifactsmmo_cli.ai.obtain_model.gate import Gate, GateKind
from artifactsmmo_cli.ai.obtain_model.policy import Policy
from artifactsmmo_cli.ai.obtain_model.ready_core import ready_routes
from artifactsmmo_cli.ai.obtain_model.route import UNBOUNDED_CAPACITY, Route
from artifactsmmo_cli.ai.obtain_model.walk_graph import WalkAnswer, WalkGraph
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.world_state import GOLD_CODE, WorldState

_MINTS = (SourceKind.CRAFT, SourceKind.GATHER, SourceKind.BUY, SourceKind.DROP,
          SourceKind.TASK_REWARD, SourceKind.GOLD_DROP)
"""Route kinds that make new copies, as opposed to moving existing ones."""

DEFAULT_SKILL_LEVEL = 1
"""A skill absent from `state.skills` is at the API's starting level (D-Q)."""


class ObtainModel:
    """All routes to any item from one snapshot of the world."""

    def __init__(self, state: WorldState, game_data: GameData,
                 ctx: SelectionContext, now: datetime) -> None:
        self._state = state
        self._gd = game_data
        self._ctx = ctx
        self._now = now
        self._routes: dict[str, tuple[Route, ...]] = {}

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
                   keep: frozenset[str] = frozenset()) -> WalkGraph:
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
        nothing ready serves (Phase 2c-2c)."""
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
            ready = self.ready(code, policy)
            gated: list[tuple[Route, tuple[Gate, ...]]] = []
            for route in self.routes(code):
                if not policy.admits(route) or route in ready:
                    continue
                unmet = tuple(gate for gate in route.gates
                              if policy.enforces(gate, route) and not gate.satisfied)
                if unmet and all(openable(gate) for gate in unmet):
                    gated.append((route, unmet))
            candidates = [(route, ()) for route in self._ranked_gathers(code, ready)] + gated
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

    def _ranked_gathers(self, item: str, ready: tuple[Route, ...]) -> list[Route]:
        """`ready` with its GATHER routes (contiguous in priority order) ranked
        by the proved gather-source order (`gather_selection`, expected gathers
        per unit, then distance to the nearest tile, then code), so the walk's
        first gather is the one `select_gather_source` picks; every other route
        keeps its place."""
        gathers = [route for route in ready if route.kind is SourceKind.GATHER]
        if len(gathers) < 2:
            return list(ready)
        candidates: list[GatherCandidate] = []
        for route in gathers:
            # A resource known only from the primary-drop map has no drop-table
            # row; `_gather` rates it 1 (a sure drop), so the candidate does too.
            row = next((r for r in self._gd.resource_drop_table(route.via) if r[0] == item),
                       (item, 1, 1, 1))
            tiles = self._gd.all_resource_locations.get(route.via) or []
            distance = min((abs(x - self._state.x) + abs(y - self._state.y) for x, y in tiles), default=0)
            candidates.append(GatherCandidate(route.via, row[1], row[2], row[3], distance))
        by_resource = {route.via: route for route in gathers}
        ranked = iter([by_resource[code] for code in rank_gather_sources(candidates)])
        return [next(ranked) if route.kind is SourceKind.GATHER else route for route in ready]

    def walk(self, item: str, qty: int, policy: Policy,
             produce: frozenset[str] = frozenset(),
             openable: Callable[[Gate], bool] = lambda _gate: False,
             keep: frozenset[str] = frozenset()) -> WalkAnswer:
        """The one walk over `item`'s closure: can `qty` be had, and the next
        step toward it (`decompose_core`)."""
        graph = self.walk_graph(item, policy, produce, openable, keep)
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
        gated one. The yield is the repeated UNIT-recycle yield
        `max(1, mat_qty // 2)`, not the batch form, which differs whenever
        `mat_qty == 1`. `LICENSED` asks the keep authority (`destroyable`) for
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
            copies = destroyable(code, self._state, self._gd, self._ctx)
            yield_per = max(1, recipe[item] // 2)
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
        """One route per resource that drops `item`, most frequent first. The
        first one is the route `GameData.resource_for_drop` picks (the first
        minimal-rate dropper in table order, falling back to the primary-drop
        map) and is marked `primary`: the only one the legacy model offered.
        The stable sort is what keeps that tie-break identical."""
        droppers = [(res, rate) for res, table in self._gd.resource_drops_full.items()
                    for code, rate, _mn, _mx in table if code == item]
        if not droppers:
            droppers = [(res, 1) for res, code in self._gd.resource_drops.items() if code == item]
        out: list[Route] = []
        for rank, (resource, _rate) in enumerate(sorted(droppers, key=lambda pair: pair[1])):
            gates = [Gate(GateKind.SPAWN_LIVE, resource,
                          bool(self._gd.all_resource_locations.get(resource))),
                     Gate(GateKind.SPAWN_KNOWN, resource, self._gd.resource_spawn_known(resource))]
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
        are evaluated (shared with `drop_obtainability`)."""
        return drop_routes(item, self._state, self._gd)

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
        return gold_drop_routes(self._state, self._gd)

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

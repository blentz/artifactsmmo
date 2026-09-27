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
CRAFT, GATHER, BUY, GE_FILL, DROP, SELL: routes that consume stock already owned
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

from datetime import datetime

from artifactsmmo_cli.ai import accumulation_sell
from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.event_availability import event_npc_tradeable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_keep import destroyable
from artifactsmmo_cli.ai.obtain_model.drop_routes import drop_routes
from artifactsmmo_cli.ai.obtain_model.feasibility import Feasibility
from artifactsmmo_cli.ai.obtain_model.feasible_core import feasible_items
from artifactsmmo_cli.ai.obtain_model.gate import Gate, GateKind
from artifactsmmo_cli.ai.obtain_model.policy import Policy
from artifactsmmo_cli.ai.obtain_model.ready_core import ready_routes
from artifactsmmo_cli.ai.obtain_model.route import UNBOUNDED_CAPACITY, Route
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.world_state import GOLD_CODE, WorldState

_OWNED = (SourceKind.WITHDRAW, SourceKind.RECYCLE)
"""Route kinds that deliver copies the character already owns."""

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
                      *self._drop(item), *self._sell(item))
            self._routes[item] = cached
        return cached

    def ready(self, item: str, policy: Policy) -> tuple[Route, ...]:
        """The routes to `item` usable right now under `policy`, in priority
        order (see `ready_core.ready_routes`, the proved selection)."""
        return ready_routes(self.routes(item), policy)

    def feasible(self, item: str, policy: Policy) -> Feasibility:
        """Can at least one unit of `item` be obtained from here under `policy`?

        The least fixpoint of `feasible_core.feasible_items` over the input
        closure of `item`'s ready routes: an item is feasible when held
        (bag, worn, or pocket gold) or when some ready route has every input
        feasible. A banked copy is not "held": it arrives as a WITHDRAW route,
        gated on bank access. Existence only; quantities are not modelled."""
        closure, ready_inputs = self._closure(item, policy, renewable_only=False)
        found = feasible_items(closure, self._held(), ready_inputs)
        if item in found:
            return Feasibility(ok=True)
        gates = tuple(gate for route in self.routes(item)
                      if policy.admits(route) and not policy.ready(route)
                      for gate in route.gates
                      if policy.enforces(gate, route) and not gate.satisfied)
        missing = tuple(dict.fromkeys(x for inputs in ready_inputs[item] for x in inputs
                                      if x not in found))
        return Feasibility(ok=False, blocking_gates=gates, missing_inputs=missing)

    def renewable(self, item: str, policy: Policy) -> bool:
        """Can `item` be made again and again under `policy`, however many
        units are wanted? True when some ready route that is not stock-limited
        (a CRAFT, GATHER, DROP or BUY) has every input renewable. Nothing held
        counts, and no WITHDRAW, RECYCLE or GE_FILL route (each can deliver only
        its `capacity`).

        The same proved least fixpoint as `feasible` (`feasible_core`), over the
        unbounded routes only and with nothing held."""
        closure, ready_inputs = self._closure(item, policy, renewable_only=True)
        return item in feasible_items(closure, frozenset(), ready_inputs)

    def on_hand(self, item: str, policy: Policy) -> int:
        """Units of `item` available from what the character already owns: the
        bag, plus the capacity of every ready WITHDRAW (banked copies) and
        RECYCLE (licensed copies) route. Not a GE fill, which is a purchase, and
        not worn copies: using one would mean unequipping it."""
        return self._state.inventory.get(item, 0) + sum(
            route.capacity for route in self.ready(item, policy) if route.kind in _OWNED)

    def _closure(self, item: str, policy: Policy, *, renewable_only: bool
                 ) -> tuple[list[str], dict[str, list[list[str]]]]:
        """`item` and every input reachable through its ready routes (only the
        unbounded ones when `renewable_only`), with each item's ready-route
        input lists: the graph `feasible_core.feasible_items` runs on."""
        closure: list[str] = []
        ready_inputs: dict[str, list[list[str]]] = {}
        pending = [item]
        while pending:
            code = pending.pop()
            if code in ready_inputs:
                continue
            closure.append(code)
            ready_inputs[code] = [list(route.inputs) for route in self.ready(code, policy)
                                  if not renewable_only or route.capacity >= UNBOUNDED_CAPACITY]
            pending.extend(x for inputs in ready_inputs[code] for x in inputs)
        return closure, ready_inputs

    def _held(self) -> frozenset[str]:
        held = {code for code, qty in self._state.inventory.items() if qty > 0}
        held.update(code for code in self._state.equipment.values() if code)
        if self._state.gold > 0:
            held.add(GOLD_CODE)
        return frozenset(held)

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
        order_id, _price, quantity = order
        gate = Gate(GateKind.GE_LOCATED, "grand_exchange",
                    self._gd.grand_exchange_location() is not None)
        return [Route(item, SourceKind.GE_FILL, order_id, 1, quantity, (gate,))]

    def _drop(self, item: str) -> list[Route]:
        """Monsters that drop `item`: see `drop_routes`, the one place drop gates
        are evaluated (shared with `drop_obtainability`)."""
        return drop_routes(item, self._state, self._gd)

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

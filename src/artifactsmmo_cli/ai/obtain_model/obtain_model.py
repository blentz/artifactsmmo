"""ObtainModel: every route to every item, with every gate evaluated.

Phase 1 of `docs/PLAN_decision_architecture_redesign.md`. One model replaces the
seventeen that each answered "can I get X / how" with a different subset of the
real gates. It enumerates ALL routes, evaluates ALL gates on each, and leaves
the choice of which gates count to an explicit `Policy`.

STEP 1 (this module's current scope): the model sits beside `obtain_sources`,
and nothing on the decision path reads it yet; only `audit/obtain_model_census.py`
does. `ready(item, LEGACY)` must equal `obtain_sources(item)` exactly, which that
census checks over every item of real game data. Decision-path code migrates
onto the model only after that holds.

Built once per decision from one `(state, game_data, ctx, now)` snapshot, and
memoised per item for its lifetime. Pure: no I/O.
"""

from dataclasses import replace
from datetime import datetime

from artifactsmmo_cli.ai import accumulation_sell
from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.event_availability import event_npc_tradeable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_keep import destroyable
from artifactsmmo_cli.ai.obtain_model.feasibility import Feasibility
from artifactsmmo_cli.ai.obtain_model.feasible_core import feasible_items
from artifactsmmo_cli.ai.obtain_model.gate import Gate, GateKind
from artifactsmmo_cli.ai.obtain_model.policy import Policy
from artifactsmmo_cli.ai.obtain_model.ready_core import ready_routes
from artifactsmmo_cli.ai.obtain_model.route import Route
from artifactsmmo_cli.ai.obtain_sources import UNBOUNDED_CAPACITY
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.world_state import GOLD_CODE, WorldState

PRIORITY: tuple[SourceKind, ...] = (
    SourceKind.WITHDRAW, SourceKind.RECYCLE, SourceKind.CRAFT, SourceKind.GATHER,
    SourceKind.BUY, SourceKind.GE_FILL, SourceKind.DROP, SourceKind.SELL)
"""The declared priority order: routes that consume stock already owned come
before routes that create new work (see `obtain_sources`' module docstring)."""

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
        # Winnability is asked at RESTORABLE hp: route existence is not an hp
        # question, and resting is an action the planner has.
        self._rested = replace(state, hp=state.max_hp)
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
        closure: list[str] = []
        ready_inputs: dict[str, list[list[str]]] = {}
        pending = [item]
        while pending:
            code = pending.pop()
            if code in ready_inputs:
                continue
            closure.append(code)
            ready_inputs[code] = [list(route.inputs) for route in self.ready(code, policy)]
            pending.extend(x for inputs in ready_inputs[code] for x in inputs)
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

    def _held(self) -> frozenset[str]:
        held = {code for code, qty in self._state.inventory.items() if qty > 0}
        held.update(code for code in self._state.equipment.values() if code)
        if self._state.gold > 0:
            held.add(GOLD_CODE)
        return frozenset(held)

    def _skill(self, skill: str) -> int:
        return self._state.skills.get(skill, DEFAULT_SKILL_LEVEL)

    def _withdraw(self, item: str) -> list[Route]:
        stock = (self._state.bank_items or {}).get(item, 0)
        if stock <= 0:
            return []
        gate = Gate(GateKind.BANK_ACCESSIBLE, "bank", self._ctx.bank_accessible)
        return [Route(item, SourceKind.WITHDRAW, item, 1, stock, (gate,))]

    def _recycle(self, item: str) -> list[Route]:
        """Held equippables whose recipe consumes `item`. A non-equippable has
        no RecycleAction in existence, so it is no route at all."""
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
        route `resource_for_drop` picks is marked `primary`: the only one the
        legacy model offered."""
        droppers = [(res, rate) for res, table in self._gd.resource_drops_full.items()
                    for code, rate, _mn, _mx in table if code == item]
        if not droppers:
            droppers = [(res, 1) for res, code in self._gd.resource_drops.items() if code == item]
        found = self._gd.resource_for_drop(item)
        primary = found[0] if found is not None else None
        out: list[Route] = []
        for resource, _rate in sorted(droppers, key=lambda pair: pair[1]):
            gates = [Gate(GateKind.SPAWN_LIVE, resource,
                          bool(self._gd.all_resource_locations.get(resource)))]
            requirement = self._gd.resource_skill_level(resource)
            if requirement is not None:
                skill, level = requirement
                gates.append(Gate(GateKind.GATHER_SKILL, skill, self._skill(skill) >= level, level))
            out.append(Route(item, SourceKind.GATHER, resource, 1, UNBOUNDED_CAPACITY,
                             tuple(gates), primary=resource == primary))
        return out

    def _buy(self, item: str) -> list[Route]:
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
        order = self._gd.ge_best_sell_order(item)
        if order is None:
            return []
        order_id, _price, quantity = order
        gate = Gate(GateKind.GE_LOCATED, "grand_exchange",
                    self._gd.grand_exchange_location() is not None)
        return [Route(item, SourceKind.GE_FILL, order_id, 1, quantity, (gate,))]

    def _drop(self, item: str) -> list[Route]:
        out: list[Route] = []
        for monster, _rate, _mn, _mx in self._gd.monsters_dropping(item):
            live = bool(self._gd.all_monster_locations.get(monster))
            gates = (
                Gate(GateKind.SPAWN_LIVE, monster, live),
                # Asked only for a live monster: a sleeping event monster has no
                # FightAction to serve it, so its verdict could never be used.
                Gate(GateKind.WINNABLE, monster,
                     live and is_winnable(self._rested, self._gd, monster)),
            )
            out.append(Route(item, SourceKind.DROP, monster, 1, UNBOUNDED_CAPACITY, gates))
        return out

    def _sell(self, item: str) -> list[Route]:
        """GOLD only: selling what the keep authority licenses, one route per
        (item sold, buyer), buyers highest price first."""
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

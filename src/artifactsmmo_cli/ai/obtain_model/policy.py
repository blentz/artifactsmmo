"""Policy: which gates a caller enforces, instead of which model it asks.

The seventeen models that preceded the obtain model differed in two ways: some
differences were bugs (a gate one model forgot), and some were legitimate
caller needs (an attainability probe may count a grey monster that an emitter
must refuse). The obtain model keeps ONE set of routes and gate verdicts, and a
`Policy` names the legitimate differences explicitly. Fixing a disagreement is
then a change to a policy default that the disagreement census can see,
rather than an edit to one of many models.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.obtain_model.gate import Gate, GateKind
from artifactsmmo_cli.ai.obtain_model.route import Route
from artifactsmmo_cli.ai.source_kind import SourceKind

_SPAWNED = (SourceKind.DROP, SourceKind.GOLD_DROP, SourceKind.GATHER)
"""The route kinds served at a spawn tile: a monster's or a resource's."""


@dataclass(frozen=True)
class Policy:
    """Which routes and gates count.

    `all_gather_routes`: offer every resource that drops the item (True) or
    only the most frequent one, as `obtain_sources` did (False; D-B).
    `gather_skill_gate`: enforce the gathering skill on GATHER routes (True)
    or ignore it, as `obtain_sources` did (False; D-A).
    `craft_skill_gate`: enforce the crafting skill on CRAFT routes (True, as
    `obtain_sources` did) or ignore it (False, as the skill grind's walk did: a
    skill gate on a rung's chain is a level the character can grind, and
    `gather_demand` surfaces it as demand). D-M replaces both skill switches
    with the gate as a sub-goal: feasible when the grind to it is.
    `event_vendors`: a vendor counts when tradeable now, event NPCs included
    (True), or only when it is a permanent NPC, as `obtain_sources` did
    (False; D-F).
    `spawn_known`: a DROP or GATHER route needs a routable spawn, a tile in a
    reachable region of any layer (True, as `drop_obtainability` asks of a
    monster), or a live overworld tile (False, as `obtain_sources` asks; D-D).
    The action pool builds fights and gathers for both kinds of tile.
    `allow_grey`: a zero-xp dropper counts (True) or not (False). The legacy
    walk had no grey rule; `drop_obtainability`'s callers choose it.
    `vendor_routes`: BUY routes are offered (True) or not (False, for a caller
    whose emission cannot serve an NPC purchase, e.g. the skill grind's descent).
    `ge_routes`: GE_FILL routes are offered (True) or not (False, for a caller
    whose emission cannot fill a GE order: goal emission offers a fill only as
    the cheaper venue for an item an NPC also sells, and building fills from the
    model's routes is Phase 2; D-E).
    `task_rewards`: a TASK_REWARD route is offered (True) or not (False, as
    `obtain_sources` did: it has no task edge; D-N).
    `fight_gold`: a GOLD_DROP route is offered (True: gold is earned by
    fighting, so a gold price is a matter of time) or not (False: gold is what
    the pocket holds or a sale raises, as `obtain_sources` and near-term
    attainability ask)."""

    all_gather_routes: bool
    gather_skill_gate: bool
    craft_skill_gate: bool
    event_vendors: bool
    spawn_known: bool
    allow_grey: bool
    vendor_routes: bool
    ge_routes: bool
    task_rewards: bool
    fight_gold: bool

    def admits(self, route: Route) -> bool:
        """Is `route` offered at all under this policy?"""
        if route.kind is SourceKind.BUY:
            return self.vendor_routes
        if route.kind is SourceKind.GE_FILL:
            return self.ge_routes
        if route.kind is SourceKind.TASK_REWARD:
            return self.task_rewards
        if route.kind is SourceKind.GOLD_DROP:
            return self.fight_gold
        return route.kind is not SourceKind.GATHER or self.all_gather_routes or route.primary

    def enforces(self, gate: Gate, route: Route) -> bool:
        """Does this policy require `gate` to be satisfied on `route`?"""
        if gate.kind is GateKind.GATHER_SKILL:
            return self.gather_skill_gate
        if gate.kind is GateKind.CRAFT_SKILL:
            return self.craft_skill_gate
        if route.kind is SourceKind.BUY and gate.kind is GateKind.VENDOR_PERMANENT:
            return not self.event_vendors
        if route.kind is SourceKind.BUY and gate.kind is GateKind.VENDOR_TRADEABLE:
            return self.event_vendors
        if route.kind in _SPAWNED and gate.kind is GateKind.SPAWN_LIVE:
            return not self.spawn_known
        if route.kind in _SPAWNED and gate.kind is GateKind.SPAWN_KNOWN:
            return self.spawn_known
        if gate.kind is GateKind.XP_POSITIVE:
            return not self.allow_grey
        return True

    def ready(self, route: Route) -> bool:
        """Is `route` usable right now under this policy?"""
        return self.admits(route) and all(
            gate.satisfied for gate in route.gates if self.enforces(gate, route))


LEGACY = Policy(all_gather_routes=False, gather_skill_gate=False, craft_skill_gate=True,
                event_vendors=False,
                spawn_known=False, allow_grey=True, vendor_routes=True, ge_routes=True,
                task_rewards=False, fight_gold=False)
"""Exactly what `obtain_sources` answers today. Phase 1 step 1 proves the model
reproduces it under this policy before any consumer moves or any D-x decision
changes behaviour."""

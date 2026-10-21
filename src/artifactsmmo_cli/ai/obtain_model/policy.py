"""Policy: which gates a caller enforces, instead of which model it asks.

The seventeen models that preceded the obtain model differed in two ways: some
differences were bugs (a gate one model forgot), and some were legitimate
caller needs (an attainability probe may count a grey monster that an emitter
must refuse). The obtain model keeps ONE set of routes and gate verdicts, and a
`Policy` names the legitimate differences explicitly. Fixing a disagreement is
then a change to a policy default that the disagreement census can see,
rather than an edit to one of many models.
"""

from dataclasses import dataclass, replace

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
    attainability ask).
    `drop_routes`: a DROP route is offered (True) or not (False, for a caller
    whose emission cannot fight: the potion supply emits no FightAction).
    `price_climbs`: a CRAFT or GATHER route whose own skill requirement exceeds
    the character's skill is priced with the climb to it even though this
    policy admits it as ready (True: the gate decides achievability, the climb
    is price; ruling T2c') or priced as the ready route the policy admits
    (False: a caller that opens a skill gate on purpose, such as the skill
    grind's ranking pricing a fish-gated rung as "gather the fish")."""

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
    drop_routes: bool
    price_climbs: bool

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
        if route.kind is SourceKind.DROP:
            return self.drop_routes
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


LEGACY = Policy(all_gather_routes=False, gather_skill_gate=True, craft_skill_gate=True,
                event_vendors=False,
                spawn_known=True, allow_grey=True, vendor_routes=True, ge_routes=True,
                price_climbs=False,
                task_rewards=False, fight_gold=False, drop_routes=True)
"""What `obtain_sources` answers: the routes the executor can serve now.
Phase 1 step 1 proved the model reproduced the old walk under this policy
before any consumer moved; each D-x decision since then changes it one switch
at a time. D-A (2026-09-27): the gathering skill is enforced, so a resource the
character cannot yet gather is no ready route (the pricer still offers it,
priced with the grind that opens it: `acquisition_cost._gated_skill_option`).
D-D (2026-09-27): a spawn counts when ROUTABLE, a tile in a reachable region
of any layer, not only a live overworld tile: the action factory builds the
fight or gather for it and the planner reaches it through a transition
(`Transition(->underground)`, then `Gather(gold_rocks)`)."""


DECOMPOSE_POLICY = replace(LEGACY, all_gather_routes=True, ge_routes=False, allow_grey=False,
                           event_vendors=True)
"""The walk's readiness: LEGACY (what the executor can serve now) with four
switches.

- An event vendor counts while it is tradeable now (`VENDOR_TRADEABLE`: its
  event live, the walk and the window allow the trade), as the action pool's
  NpcBuy does. LEGACY refused every event NPC (D-F: one was not reliably
  reachable); with its event live the conditions census found the walk
  declining what the executor could buy: demoniac_dagger's piece_of_obsidian
  from the live gemstone_merchant (2026-10-10).

- Every resource that drops an item is offered (D-B), ranked by the proved
  gather-source order. LEGACY's primary-only gather hid a workable spot behind a
  skill-gated one: `small_pearls` drops at bass (fishing 30) and salmon
  (fishing 40, the most frequent), and primary-only offered salmon alone, so
  the walk opened a fishing grind instead of gathering at bass.
- No GE fill (D-E). A fill spends gold, and whether a standing order is worth
  its price against the time a fight or gather costs is a COST question the
  model cannot answer yet (the cost view); fills stay the venue choice goal
  emission makes beside an NPC buy (`choose_buy_venue`). The old descent never
  used them either: its "ge_fill" step fell through the mapping into a fight.
- No grey dropper by default: the 2026-07-06 grey-farm directive ("grind the
  skill and craft the better item instead of farming greys for a soon-obsolete
  one") is applied per item by the walk's caller (`craft_plan_gen._walk_plan`'s
  `grey_ok`: a skill grind, a drop `grey_farm_allowed` licenses, an upgrade's
  own target), as the search's admission applied it. LEGACY allowed every grey
  dropper, so the walk fought a grey sheep for an ordinary wool demand (live
  from 2c-2b until 2026-10-02)."""


PIECE_POLICY = Policy(all_gather_routes=True, gather_skill_gate=False, craft_skill_gate=False,
                      event_vendors=True, spawn_known=True, allow_grey=True, vendor_routes=True,
                      ge_routes=True, task_rewards=True, fight_gold=True, drop_routes=True,
                      price_climbs=True)
"""The ONE policy an `L*` piece is judged, priced and served under
(docs/superpowers/specs/2026-10-18-global-gear-objective-design.md §2.1,
§2.3, §2.4): what the global gear objective counts as achievable
(`gear_objective.achievable`), what it prices a piece by
(`gear_objective._price`) and what the step graph counts as a leaf it can
produce (`tiers/strategy.actionable_step`). Three policies answered those
three questions before (plan B), and they disagreed: `lich_race_trophy` was
achievable through its live event vendor and then declined `no_step_goal`,
because the step graph refused every event NPC.

- No skill gate on a GATHER or CRAFT route: any skill level is climbable, so a
  climb is a cost, never a veto (`price_climbs`: the price carries it).
- An event vendor counts while it is tradeable now, and an event monster only
  while its event is live: event-only routes are not completable otherwise.
- A standing GE sell order counts while it stands (USER 2026-10-19: "yes, live
  sell order counts as a route just like an event"). The route exists only
  while the book holds an open sell order (`ObtainModel._ge_fill` reads
  `ge_best_sell_order`, None when the order is gone), as an event vendor's
  route is ready only while `VENDOR_TRADEABLE` holds.
- A routable spawn (`spawn_known`): a tile on any layer in a reachable region.
  It admits a static underground or interior monster, which the overworld-only
  live index cannot see, and it does NOT admit an event monster whose event is
  not live: `monster_spawn_known` reads the event tiles only while the event is
  live, and an event's candidate maps carry no static content in the map data.
- Grey droppers count: the objective asks what can be had, not what pays XP.
- Gold is earned by fighting (`fight_gold`), and task-earned currency counts:
  a vendor leaf is a step the character can work toward however far the
  pocket falls short.

The WINNABLE gate on a drop is the caller's projected fighter, not the worn
gear (`ObtainModel(..., fighter=...)`, §2.3)."""

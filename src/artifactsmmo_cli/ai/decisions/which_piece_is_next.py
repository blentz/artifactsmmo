"""The root walk's entry (spec 2026-10-18 §2.4): the next missing `L*` piece.

`ctx.gear_objective` is the cycle's `(L*, m*)`, computed once by the player.
While a piece of `L*` is missing the root is the next step on its acquisition
plan; only once `L*` is held does the character grind character XP, on `m*`.
A level-up is not an acquisition step (§6.2), so no `ReachCharLevel` heads the
walk while a piece is missing — except, INTERIM (ruling AI), when every missing
piece's step is declined and no gear action is available at all.

A crafter's fleet pieces (§2.5, `fleet_pieces`) join its own missing pieces: the
objective is held only when both are served, so the trunk is never offered
while fleet demand its role serves exists.
"""

from fractions import Fraction

# MODULE import, the idiom `root.py` uses on its own cycles: `root` imports
# this module to build its entry, so whichever of the two is reached first
# executes while the other is half built, and a NAME import of `RootWalk` /
# `IsThisTargetBlocked` would raise ImportError. Binding the module object
# defers the lookups to CALL time.
from artifactsmmo_cli.ai.decision import Decision
from artifactsmmo_cli.ai.decisions import root as _root
from artifactsmmo_cli.ai.decisions import route as _route
from artifactsmmo_cli.ai.equipment.loadout_picker import _ordered_slots
from artifactsmmo_cli.ai.fleet_piece import FleetPiece
from artifactsmmo_cli.ai.fleet_work import FLEET_SUPPLY, supply_due
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective_core import PieceKey, piece_order_key
from artifactsmmo_cli.ai.gear_objective_result import GearObjective, GearPiece
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.obtain_model.policy import PIECE_POLICY
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachFleetOutcome,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, GearTarget
from artifactsmmo_cli.ai.tool_objective import tool_first
from artifactsmmo_cli.ai.world_state import WorldState


def next_level(state: WorldState, game_data: GameData) -> ReachCharLevel | None:
    """The trunk: one more character level, or None at the API's level cap
    (`GameData.max_character_level`, final review F12). A `ReachCharLevel`
    above the cap can never be satisfied, and the character would grind `m*`
    for XP the game no longer awards."""
    if state.level >= game_data.max_character_level:
        return None
    return ReachCharLevel(level=state.level + 1)


def piece_target(piece: GearPiece, objective: CharacterObjective, state: WorldState) -> GearTarget:
    """The piece's target as the route that priced it serves it (plan B Task
    3), for the walk's entry and the alternatives `resolve_root` offers alike.
    A crafted piece (`GearPiece.crafted`) is classified (`classify_target`:
    the crafting gate first, then the materials). Any other route is the piece
    itself, its own blocker, so `IsThisTargetBlocked` roots `ObtainItem(code,
    1, slot)` and the step graph owns the rest: a piece the book or a vendor
    sells is bought, never climbed to (cell 5's amulet, 213 gold on the book,
    once rooted the jewelrycrafting climb its craft needs)."""
    if piece.crafted:
        return objective.classify_target(piece.code, state)
    return GearTarget(code=piece.code, attainable=False, blocker=piece.code)


def fleet_piece_root(piece: FleetPiece, state: WorldState, game_data: GameData,
                     ctx: SelectionContext) -> MetaGoal:
    """The step a fleet piece (§2.5) asks of the crafter now: the next level of
    its craft skill while the gate is unmet (+1, as `IsThisTargetBlocked`
    climbs: the walk re-derives every cycle); once met, the supply run that
    banks it for the receivers when it is this cycle's due supply target
    (`fleet_work.supply_due`), else its craft — one unit made, which the
    supply run then banks (ruling T7d M3: a met gate is a craft, never no
    step, so a crafter whose only work is the fleet's never idles on it)."""
    current = state.skills[piece.skill]
    if current < piece.level:
        return tool_first(ReachSkillLevel(skill=piece.skill, level=current + 1),
                          state, game_data, ctx)
    target = ctx.supply_target
    if target is not None and target[0] == piece.code and supply_due(ctx):
        return ReachFleetOutcome(FLEET_SUPPLY, piece.code)
    return ObtainItem(piece.code, 1)


def pursuit_order(target: GearObjective, fleet: tuple[FleetPiece, ...], state: WorldState,
                  game_data: GameData, ctx: SelectionContext,
                  history: LearningStore | None) -> list[GearPiece | FleetPiece]:
    """The crafter's joint objective in pursuit order (spec 2026-10-18 §2.5):
    its own missing pieces and its fleet pieces, by the one `piece_order_key`.

    Without fleet pieces this is `missing` itself, never re-sorted (its order
    IS that key). A fleet piece is keyed as a crafter's own piece is: layer 0
    (it is the crafter's own craft, the climb priced in), its gain summed over
    the receivers, its price the crafter's `route_price` of one unit under
    `PIECE_POLICY` (the policy an `L*` piece is priced by), and a slot rank
    behind every slot (it fills none of the crafter's slots), so on a full tie
    the crafter's own piece goes first. One price per fleet piece: the call
    budget `decisions/route` sets."""
    if not fleet:
        return list(target.missing)
    rank = _ordered_slots()
    keyed: list[tuple[PieceKey, GearPiece | FleetPiece]] = [
        (piece_order_key(piece.layer, piece.gain, piece.price, rank.index(piece.slot)), piece)
        for piece in target.missing]
    for piece in fleet:
        price = Fraction(_route.route_price(ObtainItem(piece.code, 1), state, game_data, ctx,
                                            history, policy=PIECE_POLICY))
        keyed.append((piece_order_key(0, piece.gain, price, len(rank)), piece))
    # Stable: equal keys keep `missing`'s order, then the board's.
    return [piece for _key, piece in sorted(keyed, key=lambda pair: pair[0])]


class WhichPieceIsNext(Decision[MetaGoal]):
    """Which missing `L*` piece does the character acquire next?

    * `L*` held (§2.4.1): `ReachCharLevel(state.level + 1)` (none at the
      level cap, `next_level`), whose step fights
      `m*` (`ctx.combat_monster` is `m*` exactly while `L*` is held). One level,
      not a milestone: `(L*, m*)` is recomputed every cycle, so a level-up that
      makes better gear legal retargets the very next cycle.
    * a piece missing (§2.4.2): the FIRST piece, in `missing`'s own order
      (layer, then gain per price — never re-sorted here), whose step can be
      served this cycle (`RootWalk.serves`) goes to `IsThisTargetBlocked`,
      served by the route that priced it (`piece_target`): a crafted piece's
      crafting-skill gate becomes the next skill level, a missing material its
      `ObtainItem`; a piece priced by any other route is its own
      `ObtainItem`. A piece whose step is declined is recorded with its reason
      and the next piece is asked, and so is a piece a sibling crafts for this
      character (`GearPiece.awaits_delivery`, §2.5) until its copy is banked.
    * every piece declined (INTERIM, ruling AI): no gear action is available
      this cycle, so XP is the next action that best advances the character
      (§2.4), and the root is `ReachCharLevel(state.level + 1)` on `m*`.
    * no objective: the wall, `None` — no achievable loadout pays XP on any
      monster, so there is neither a piece to build nor a fight to grind.
    * a crafter's fleet pieces (§2.5, `ctx.fleet_pieces`) are pursued beside its
      own, in `pursuit_order`: a piece's step is its climb, then its supply
      run or its craft once the gate is met (`fleet_piece_root`). While one waits the trunk is
      withheld, `L*` held or every piece declined: a crafter is never pulled
      off its role to grind XP while the fleet has demand it serves.

    A missing piece the decision's game data does not know RAISES: the
    objective and the catalogue disagree, which is a data fault, and a root
    classified against other data would hide it (API data or fail).
    """

    name = "WhichPieceIsNext"

    def __init__(self, objective: CharacterObjective, walk: "_root.RootWalk") -> None:
        self.objective = objective
        self.walk = walk

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision[MetaGoal] | MetaGoal | None":
        self.walk.trail.append(self.name)
        target = ctx.gear_objective
        if target is None:
            return None
        fleet = ctx.fleet_pieces
        if target.held and not fleet:
            return next_level(state, game_data)
        unknown = [piece.code for piece in target.missing
                   if game_data.item_stats(piece.code) is None]
        if unknown:
            # API data or fail: a piece the decision's catalogue does not know
            # is a data fault, never a root classified against other data.
            raise ValueError(f"gear objective names {unknown!r}, absent from game data")
        for piece in pursuit_order(target, fleet, state, game_data, ctx, history):
            if isinstance(piece, FleetPiece):
                root = fleet_piece_root(piece, state, game_data, ctx)
                reason = self.walk.step_decline(root)
                if reason is None:
                    return root
                self.walk.declined[repr(root)] = reason
                continue
            if piece.awaits_delivery(state):
                # A sibling crafts it for us (§2.5): the piece waits on the
                # bank, and the walk asks the next one.
                self.walk.declined[repr(ObtainItem(piece.code, 1, slot=piece.slot))] = (
                    "awaits the fleet crafter")
                continue
            gear = piece_target(piece, self.objective, state)
            if self.walk.serves(piece.slot, gear, state, game_data, ctx, history):
                return _root.IsThisTargetBlocked(piece.slot, gear, self.walk)
        if fleet:
            # Fleet demand this role serves is waiting, and none of its steps
            # can be served this cycle: no XP fight, so no root.
            return None
        # INTERIM (ruling AI, final review F1): every missing piece is declined,
        # so no gear step can be served. Returning None here shut the XP trunk
        # off for good whenever a piece the obtain model calls feasible maps to
        # no goal the walk can serve (live: `lich_race_trophy`, `no_step_goal`,
        # heads 3 of 5 objectives). Plan B must make the obtain model and the
        # walk agree, so `L*` never names such a piece; until then the trunk is
        # offered behind the declined pieces, which stay in `declined` by name.
        return next_level(state, game_data)

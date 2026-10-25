"""The fleet pieces a crafter serves (spec 2026-10-18 §2.5, "the crafter's own
objective").

For a character holding a craft role, climbing its role skill and crafting
fleet pieces IS an acquisition step: every `L*` piece a sibling publishes on the
board whose craft is gated on the role's craft skill joins the crafter's own
missing pieces, ordered by the same `piece_order_key` with its gain summed over
the receivers. So the crafter is never pulled off its role to grind XP while
the fleet has demand it serves.

Computed ONCE per cycle by the player onto `SelectionContext.fleet_pieces`, the
one value every consumer reads — the root walk's entry (`WhichPieceIsNext`),
its alternatives (`resolve_root`) and the grind target
(`gear_objective_context.farm_target`) — so the three cannot disagree about
whether fleet demand is waiting.
"""

from collections.abc import Mapping
from fractions import Fraction

from artifactsmmo_cli.ai.fleet_piece import FleetPiece
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.role_catalog import ROLES_BY_NAME
from artifactsmmo_cli.ai.world_state import WorldState


def fleet_pieces(state: WorldState, game_data: GameData, role: str | None,
                 board: Mapping[str, tuple[int, Fraction]]) -> tuple[FleetPiece, ...]:
    """The pieces on `board` (code -> (units, summed gain), the siblings' `L*`
    pieces) that the craft skill of `role` makes, in board order.

    None without a role: a character holds no fleet objective until it holds
    the role (`role_selection.decide_role` gives a craft role only to the
    fleet's climber for that skill). A code this character holds in its bag or
    bank is not one: a held copy is supplied by a deposit (the supply run,
    `ReachFleetOutcome`), not by a climb or a craft."""
    if role is None:
        return ()
    skill = ROLES_BY_NAME[role].craft
    banked = state.bank_items or {}
    pieces: list[FleetPiece] = []
    for code, (_units, gain) in board.items():
        requirement = game_data.producing_requirement(code)
        if requirement is None or requirement[0] != skill:
            continue
        if state.inventory.get(code, 0) > 0 or banked.get(code, 0) > 0:
            continue
        pieces.append(FleetPiece(code, skill, requirement[1], gain))
    return tuple(pieces)

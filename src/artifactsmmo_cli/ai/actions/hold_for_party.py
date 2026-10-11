"""HoldForPartyAction: go to a party lease's tile and hold there for the
leader's fight (docs/PLAN_group_fights.md increment 4).

The server lets a leader fight a boss with `participants` only while every
participant stands on the boss tile out of cooldown (HTTP 486 / 499, live
probe 2026-10-11). A member named by a live lease, and a leader whose party
is not assembled yet, spend their cycle here: move to the tile if off it, then
pause `HOLD_SECONDS` and read the character back — the leader's fight changes
it server-side (XP, gold, drops, HP, cooldown), so the cycle records what
the party fight paid this member.

A productive step, not `Wait`: `JoinPartyGoal` is satisfied by the hold
(`WorldState.party_held`), and the lease's end — the leader's fight or its
expiry — is the world's answer, as a cancel's removal is for `GE_CANCEL`."""

import time
from dataclasses import dataclass, replace
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.cost_core import travel_seconds
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.party_lease_core import PartyLease, on_tile
from artifactsmmo_cli.ai.world_state import WorldState

HOLD_SECONDS = 20
"""One hold's pause. A party boss fight's cooldown runs 45-180 s (the probes
and `party_loop`), so a member reads its state back a few times per fight —
one character read per hold, on the per-IP request budget."""


@dataclass
class HoldForPartyAction(Action):
    """Move to the lease tile and hold for the party fight (see the module doc)."""

    tags: ClassVar[frozenset[str]] = frozenset({"combat"})

    lease: PartyLease
    travel_region: str = "overworld"

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return state.layer == self.lease.layer

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        return replace(state, x=self.lease.x, y=self.lease.y, party_held=self.lease.boss)

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        return travel_seconds((state.x, state.y), (self.lease.x, self.lease.y)) + HOLD_SECONDS

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if not on_tile(state, self.lease):
            return MoveAction(x=self.lease.x, y=self.lease.y).execute(state, client)
        time.sleep(HOLD_SECONDS)
        result = Action._raise_for_error(get_character(client=client, name=state.character),
                                         f"HoldForParty {self.lease.boss}")
        return WorldState.from_character_schema(
            result.data, bank_items=state.bank_items, bank_gold=state.bank_gold,
            pending_items=state.pending_items, active_events=state.active_events,
            raids=state.raids)

    def __repr__(self) -> str:
        return f"HoldForParty({self.lease.boss})"

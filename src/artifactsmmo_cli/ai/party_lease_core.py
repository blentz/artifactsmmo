"""Pure core: a party lease and whether its party is assembled
(docs/PLAN_group_fights.md increment 4).

A lease names a boss, its leader, the members the leader takes along and
the tile they meet on (`CoordinationStore.claim_party`). The leader may fight
only when the party is ASSEMBLED: every member's card fresh, on the lease
tile and out of cooldown at `now` — the server refuses a member off the tile
(HTTP 486) or in cooldown (HTTP 499), live probe 2026-10-11."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from artifactsmmo_cli.ai.world_state import WorldState


@dataclass(frozen=True)
class PartyLease:
    """A live party lease (see the module doc)."""

    boss: str
    leader: str
    members: tuple[str, ...]
    layer: str
    x: int
    y: int


def on_tile(state: WorldState, lease: PartyLease) -> bool:
    """`state` stands on the lease's tile."""
    return (state.layer, state.x, state.y) == (lease.layer, lease.x, lease.y)


def ready(state: WorldState, lease: PartyLease, now: datetime) -> bool:
    """`state` is on the tile and out of cooldown at `now`."""
    return on_tile(state, lease) and (state.cooldown_expires is None
                                      or state.cooldown_expires <= now)


def assembled(lease: PartyLease, cards: Mapping[str, WorldState], now: datetime) -> bool:
    """Every member of `lease` has a live card that is `ready` at `now`."""
    return all(name in cards and ready(cards[name], lease, now) for name in lease.members)

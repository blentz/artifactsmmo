"""One active event as the active-events read (`GET /events/active`) gives it."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LiveEvent:
    """When the event ends, and the map tiles `(x, y, layer)` it stands on now.

    An event lists several candidate maps in the catalogue (`GET /events`) but
    stands on one per instance (`ActiveEventSchema.map_`), and while it lasts
    that tile's own content is gone: corrupted_owlbear takes one of owlbear's
    two tiles (live 2026-10-18)."""

    expiration: datetime
    maps: tuple[tuple[int, int, str], ...]

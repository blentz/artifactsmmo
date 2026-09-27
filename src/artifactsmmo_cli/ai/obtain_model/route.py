"""Route: one way to obtain an item, whether or not it is usable right now."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from artifactsmmo_cli.ai.obtain_model.gate import Gate
from artifactsmmo_cli.ai.source_kind import SourceKind


@dataclass(frozen=True)
class Route:
    """One way to obtain `item`, with every gate on it evaluated.

    `via` is what the route acts on, exactly as `obtain_sources.Source.code`
    names it: the item itself (WITHDRAW, CRAFT), the item destroyed (RECYCLE)
    or sold (SELL), the resource (GATHER), the vendor (BUY), the order id
    (GE_FILL) or the monster (DROP). `agent` is the NPC a SELL route sells to,
    and empty otherwise.

    `yield_per` units of the item per application; `capacity` the most units
    it can deliver right now (`obtain_sources.UNBOUNDED_CAPACITY` when not
    stock-limited). `inputs` is what one application consumes: a CRAFT
    route's recipe, or a BUY route's `{currency: price}`.

    `primary` marks the one GATHER route the legacy model offered (the most
    frequent dropper); it is True on every non-GATHER route."""

    item: str
    kind: SourceKind
    via: str
    yield_per: int
    capacity: int
    gates: tuple[Gate, ...]
    inputs: Mapping[str, int] = field(default_factory=dict)
    agent: str = ""
    primary: bool = True

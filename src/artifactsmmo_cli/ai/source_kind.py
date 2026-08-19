"""`SourceKind` — the six ways an item can be obtained.

Extracted from `obtain_sources` in Wave 2 of the requirement-model unification
epic. It lives alone because it is a pure enum with no dependencies, while
`obtain_sources` imports the action stack (`actions.equip` -> `actions.base` ->
`GameData`). Anything wanting to NAME a source route had to drag that whole
graph in, which closes an import cycle for any module `GameData` itself imports.

`obtain_sources` re-exports this name, so every existing
`from artifactsmmo_cli.ai.obtain_sources import SourceKind` keeps working and
there is exactly one enum, not two.
"""

from __future__ import annotations

from enum import Enum


class SourceKind(Enum):
    """The ways an item can be obtained, in ascending order of "creates new
    work" — see `obtain_sources` for the declared priority policy.

    SELL is the odd one and obtains exactly one thing: GOLD. It was added
    because gold is an INPUT — a gold-priced vendor route carries
    `inputs={"gold": price}` — and an input with no route is charged
    `UNOBTAINABLE_PER_UNIT` per unit. With no way to obtain gold, a shortfall of
    430 gold priced at 430,000,002 actions, so no gold-priced route in the game
    could survive a comparison the moment the purse was a coin short. Selling is
    how the bot gets gold, so selling is the route (S-046: gold is worth the
    cycles it saves, at a rate read off live prices)."""

    WITHDRAW = "withdraw"
    RECYCLE = "recycle"
    CRAFT = "craft"
    GATHER = "gather"
    BUY = "buy"
    DROP = "drop"
    SELL = "sell"

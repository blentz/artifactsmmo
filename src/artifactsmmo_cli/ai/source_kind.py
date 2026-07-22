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
    """The six ways an item can be obtained, in ascending order of "creates
    new work" — see `obtain_sources` for the declared priority policy."""

    WITHDRAW = "withdraw"
    RECYCLE = "recycle"
    CRAFT = "craft"
    GATHER = "gather"
    BUY = "buy"
    DROP = "drop"

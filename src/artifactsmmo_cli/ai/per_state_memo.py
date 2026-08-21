"""`per_state` — a one-entry identity memo for a whole-state helper.

THE PATTERN IT REMOVES. The keep authority asks its reasons once per CODE, and
several of those reasons answer a question about the WHOLE state: which held
items are heals, which weapon is best, which tools are best. Each such helper
rescans the bag, so one `select_bank_deposits` sweep over 120 holdings ran them
120 times over one unchanged bag — an O(codes x holdings) cost where
O(holdings) would do. This is the same shape as `obtain_sources._recycle_sources`
scanning every held code per call, and it is the reason a planner node cost tens
of milliseconds on a full bag.

WHY NOT A VALUE KEY. `kit_selection._pick_weapon` and `_pick_tools` already
memoise on `frozenset(candidates)` and still cost, because BUILDING that key is
itself O(holdings) and it was built once per code. A memo whose key costs as much
as the work it saves buys nothing; identity costs one pointer comparison.

WHAT IDENTITY GIVES UP. An equal-but-distinct state recomputes. That is the
conservative direction — never a stale answer for a different state — and it
matches how the planner actually calls: one state object, swept over many codes,
then discarded.
"""

from collections.abc import Callable
from functools import wraps
from typing import TypeVar

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState

_T = TypeVar("_T")


def per_state(fn: "Callable[[WorldState, GameData], _T]"
              ) -> "Callable[[WorldState, GameData], _T]":
    """Memoise `fn` on the IDENTITY of its `(state, game_data)` pair, one entry.

    `game_data` is part of the key because the catalog decides the answer, and a
    state-only key served one test's items to another once already (the six
    `test_bank_selection_diff` failures recorded on `kit_selection._tool_caches`).

    One entry, because the pattern is a sweep over codes at a single node; a
    longer history would hold states alive for nothing.

    The entry is read ONCE into a local before it is inspected, so a concurrent
    replacement cannot be observed half-applied.
    """
    slot: list[tuple[WorldState, GameData, _T]] = []

    @wraps(fn)
    def wrapper(state: WorldState, game_data: GameData) -> _T:
        entry = slot[0] if slot else None
        if entry is not None and entry[0] is state and entry[1] is game_data:
            return entry[2]
        out = fn(state, game_data)
        slot[:] = [(state, game_data, out)]
        return out

    return wrapper

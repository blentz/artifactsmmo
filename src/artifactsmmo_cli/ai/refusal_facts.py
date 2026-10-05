"""The fleet's categorical refusals, as model facts (Phase 5-1).

Replaces the per-process `DoomedMemo` that re-probed a refused action on a
20→160-cycle timer. A refusal is recorded once, fleet-wide, in the learning DB
(`refusal_fact`), and the planner's refusal filter asks it whether an action is
still refused (`refusal_fact_core.refusal_holds`).
"""

from artifactsmmo_cli.ai.action_rejection import rejection_key
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.refusal_fact_core import refusal_holds
from artifactsmmo_cli.ai.world_state import WorldState


class RefusalFacts:
    """Recorded refusals keyed by `action_rejection.rejection_key`
    (`"<ActionClass>:<item code>"`), each with its HTTP code and the item's
    game-data type when refused."""

    def __init__(self, history: LearningStore | None) -> None:
        self._history = history
        self._facts: dict[str, tuple[int, str | None]] = {}

    def load(self) -> None:
        """Read the fleet's facts from the learning DB (no store: none)."""
        if self._history is None:
            return
        self._facts = {f"{row.action_kind}:{row.item_code}": (row.http_code, row.item_type)
                       for row in self._history.load_refusal_facts()}

    def record(self, action: object, http_code: int, game_data: GameData) -> str | None:
        """Record a categorical refusal of `action`; returns its key, or None
        for an action that names no item."""
        key = rejection_key(action)
        if key is None:
            return None
        kind, code = key.split(":", 1)
        stats = game_data.item_stats(code)
        item_type = stats.type_ if stats is not None else None
        self._facts[key] = (http_code, item_type)
        if self._history is not None:
            self._history.save_refusal_fact(kind, code, http_code, item_type)
        return key

    def refused(self, action: object, state: WorldState, game_data: GameData) -> bool:
        """Does a recorded refusal still close this action?"""
        key = rejection_key(action)
        if key is None or key not in self._facts:
            return False
        http_code, recorded_type = self._facts[key]
        code = key.split(":", 1)[1]
        stats = game_data.item_stats(code)
        current_type = stats.type_ if stats is not None else None
        worn = code in state.equipment.values()
        return refusal_holds(http_code, recorded_type, current_type, worn)

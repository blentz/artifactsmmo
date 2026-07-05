"""Action ABC for GOAP planning."""

from abc import ABC, abstractmethod
from typing import ClassVar, TypeVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.models.error_response_schema import ErrorResponseSchema

from artifactsmmo_cli.ai.actions.api_action_error import ApiActionError
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

T = TypeVar("T")


class Action(ABC):
    """Abstract base class for all GOAP actions."""

    @staticmethod
    def _raise_for_error(result: T | ErrorResponseSchema | None, context: str) -> T:
        """Raise if result is an error or missing data; otherwise return the success result.

        Raises ApiActionError carrying the HTTP status code so callers can
        distinguish cooldown (499) from other errors structurally.
        """
        if isinstance(result, ErrorResponseSchema):
            raise ApiActionError(result.error.code, result.error.message)
        if result is None or not hasattr(result, "data") or result.data is None:
            raise RuntimeError(f"{context}: no response data")
        return result

    @abstractmethod
    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        """Return True if this action can be taken from the given state."""

    travel_region: str = "overworld"
    """Access region this action's folded movement stays inside (P5b).
    Every action folds move-to-target into cost/execute, which is only valid
    WITHIN one access region (same layer, no restricted boundary). The
    planner rejects actions whose region differs from the character's
    current region; TransitionAction is the sole region-crossing edge.
    Class-level default keeps every legacy action overworld-bound; layered
    Fight/Gather instances and transitions override per instance."""

    tags: ClassVar[frozenset[str]] = frozenset()
    """Semantic labels for goal-level action filtering. Subclasses override.

    Goals use `if action.tags & {"combat"}: ...` instead of long isinstance
    chains. Lets new action classes plug into existing goals by inheriting
    the right tag(s) without editing every relevant_actions() method.

    Tag vocabulary (kept small on purpose):
      combat, gather, craft, movement, recovery, bank, task, npc, equip,
      cleanup, claim, produces_char_xp, produces_skill_xp.

    ClassVar so dataclass-decorated subclasses don't treat it as a field.
    """

    @abstractmethod
    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        """Return new WorldState after applying this action's effects (no API calls)."""

    @abstractmethod
    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        """Estimated seconds. Optional `history` lets subclasses consult learned stats."""

    @abstractmethod
    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        """Call the API and return updated WorldState built from the response."""

    def __repr__(self) -> str:
        return self.__class__.__name__

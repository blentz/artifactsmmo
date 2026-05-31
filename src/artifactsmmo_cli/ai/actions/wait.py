"""WaitAction: no-op action for the WaitGoal last-resort fallback.

When every other goal is unplannable, WaitGoal/WaitAction provides a firing
candidate so the StrategyArbiter never returns (None, [], []) and the bot
spends the cycle waiting instead of stalling indefinitely.

The action is always applicable, leaves WorldState unchanged, carries a very
high planning cost so any other action wins ties in the planner, and makes
no API call on execute.
"""

from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

WAIT_COST = 1000.0
"""Large constant cost: any real action's cost (combat ~30s, gather ~10s, rest
~10s) easily beats this so WaitAction only wins when nothing else is
applicable."""


class WaitAction(Action):
    """No-op last-resort action. State unchanged; no API call."""

    tags: ClassVar[frozenset[str]] = frozenset({"cleanup"})

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return True

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        return state

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        return WAIT_COST

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        return state

    def __repr__(self) -> str:
        return "Wait"

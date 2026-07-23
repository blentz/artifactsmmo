"""AcceptTaskGoal: accept a new task when the character has none."""

from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


class AcceptTaskGoal(Goal):
    """Accept a new task when the character has none.

    When a taskmaster has been CHOSEN (synergy Wave 4, `taskmaster_choice`), the
    goal carries that master's `(location, code)` and walks there; otherwise it
    falls back to whichever `AcceptTaskAction` the factory prebuilt (today's
    single default master). The master choice never enters `__repr__`, so it
    cannot churn arbiter identity (the currency-grind sticky-keying lesson)."""

    def __init__(self, taskmaster_location: tuple[int, int] | None = None,
                 taskmaster_code: str = "monsters") -> None:
        self._taskmaster_location = taskmaster_location
        self._taskmaster_code = taskmaster_code

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Only AcceptTaskAction can satisfy this goal — it self-moves to the
        taskmaster and accepts in one step. Inheriting the base (whole ~1908-action
        pool) made the planner branch over every action and explode to 26K nodes /
        timeout when the arbiter reached this goal (l35_boots_drop_farm,
        2026-07-15) — the same bug DepositInventoryGoal already fixed with a
        relevant_actions filter. Restricting the pool keeps the search a single
        node.

        A chosen master builds its own single action (the factory prebuilds only
        the default master); an unparameterised goal filters the prebuilt pool,
        reproducing today's behaviour exactly."""
        if self._taskmaster_location is not None:
            return [AcceptTaskAction(taskmaster_location=self._taskmaster_location,
                                     taskmaster_code=self._taskmaster_code)]
        return [a for a in actions if isinstance(a, AcceptTaskAction)]

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return 20.0

    def is_satisfied(self, state: WorldState) -> bool:
        return bool(state.task_code)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"task_code": "__pending__"}

    def __repr__(self) -> str:
        return "AcceptTask"

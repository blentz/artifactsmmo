"""EquipOwnedGoal: equip owned positive-value gear into empty equipment slots.

The fill target is computed by the arbiter mapper (pick_loadout(Rank) restricted
to empty slots) and passed in, because Goal.is_satisfied receives no game_data —
mirroring the precomputed-target pattern in goals/progression.py. The goal owns
the equip decision as a first-class objective, so it fires independent of the
FightAction/GatherAction re-arm cost economics (LOADOUT_PENALTY < OptimizeLoadout
cost) that otherwise leave owned gear unequipped.
"""

from dataclasses import dataclass, field

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

EQUIP_GEAR_VALUE = 60.0
"""Priority between the grind/step ceiling (45) and the survival guard floor (70).
Placed in the COLLECT band by the arbiter, so it outranks the step/grind goal and
free gear equips before more grinding, without preempting survival/combat guards."""


@dataclass
class EquipOwnedGoal(Goal):
    """Equip each owned item in `fills` into its (currently empty) slot."""

    fills: dict[str, str] = field(default_factory=dict)

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return 0.0 if self.is_satisfied(state) else EQUIP_GEAR_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        return all(state.equipment.get(slot) == code for slot, code in self.fills.items())

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"equipment": dict(self.fills)}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        return [EquipAction(code=code, slot=slot) for slot, code in self.fills.items()]

    def __repr__(self) -> str:
        return f"EquipOwnedGear({sorted(self.fills.items())})"

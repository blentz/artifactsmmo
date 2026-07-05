"""WithdrawToolsGoal: ferry strictly-better banked gathering tools into the bag.

The fill target is computed by the arbiter mapper (`bank_tool_fills`) and
passed in, because Goal.is_satisfied receives no game_data — the same
precomputed-target pattern as EquipOwnedGoal. The goal only WITHDRAWS: once the
tool is owned, the proven gather re-arm (GATHER_LOADOUT_PENALTY in
GatherAction.cost + OptimizeLoadout(Gather)) equips it on the next gather plan,
and the bank-deposit keep-set (`bank_selection._best_gathering_tools`) stops it
from ping-ponging back into the bank.
"""

from dataclasses import dataclass, field

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

WITHDRAW_TOOLS_VALUE = 60.0
"""Not a selection driver: select_pure orders candidates by BAND + list
position, not by value() (same contract as EQUIP_GEAR_VALUE). The arbiter
places WithdrawToolsGoal in the COLLECT band so an owned-but-banked efficiency
tool is fetched before more grinding, while still yielding to survival/combat
guards. value() exists purely for API conformance and diagnostics."""


@dataclass
class WithdrawToolsGoal(Goal):
    """Withdraw each tool in `fills` (skill -> code) from the bank."""

    fills: dict[str, str] = field(default_factory=dict)
    bank_location: tuple[int, int] = (0, 0)
    accessible: bool = True

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return 0.0 if self.is_satisfied(state) else WITHDRAW_TOOLS_VALUE

    def _held(self, state: WorldState, code: str) -> bool:
        return (state.inventory.get(code, 0) > 0
                or code in state.equipment.values())

    def is_satisfied(self, state: WorldState) -> bool:
        return all(self._held(state, code) for code in self.fills.values())

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"tools_held": tuple(sorted(set(self.fills.values())))}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        return [
            WithdrawItemAction(code=code, quantity=1,
                               bank_location=self.bank_location,
                               accessible=self.accessible)
            for code in sorted(set(self.fills.values()))
            if not self._held(state, code)
        ]

    def __repr__(self) -> str:
        return f"WithdrawTools({sorted(self.fills.items())})"

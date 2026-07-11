"""UnlockBankGoal: fight to satisfy the achievement required to access the bank."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.thresholds import PRESSURE_HIGH_FRACTION
from artifactsmmo_cli.ai.world_state import WorldState


class UnlockBankGoal(Goal):
    """Fight monsters to satisfy the achievement gating bank access (HTTP 496)."""

    def __init__(self, bank_locked: bool, initial_xp: int, target_monster: str | None = None) -> None:
        self._bank_locked = bank_locked
        self._initial_xp = initial_xp
        self._target_monster = target_monster

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if not self._bank_locked or state.xp > self._initial_xp:
            return 0.0
        # If the target monster is known to be unreachable (way over-level), don't
        # fire at all — burning chickens won't satisfy the achievement and just
        # creates a loop. Defer until char levels up enough to attempt the target.
        if self._target_monster_is_unreachable(state, game_data):
            return 0.0
        # If inventory is critical AND we have a faster way to free it (NPC sell),
        # defer to SellInventoryGoal — selling is faster than grinding achievement.
        if state.inventory_max > 0:
            used_fraction = state.inventory_used / state.inventory_max
            if used_fraction >= PRESSURE_HIGH_FRACTION:
                has_sellable = any(
                    game_data.npcs_buying_item(code)
                    for code, qty in state.inventory.items() if qty > 0
                )
                if has_sellable:
                    return 30.0   # defer to SellInventoryGoal (caps at 100)
        return 90.0

    def is_satisfied(self, state: WorldState) -> bool:
        # Planner-reachable satisfaction: one target-monster fight bumps XP.
        # `not _bank_locked` is a flag set at construction, never changed by
        # any simulated action, so it left the planner unable to ever reach a
        # satisfied node → plan_len=0 every cycle and this priority-90 goal
        # silently lost. relevant_actions restricts combat to the TARGET
        # monster only, so `xp > initial_xp` can only be reached by fighting
        # the right monster — killing a chicken can no longer satisfy it.
        if not self._bank_locked:
            return True
        return state.xp > self._initial_xp

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {}

    def relevant_actions(self, actions: list[Action], state: WorldState, game_data: GameData) -> list[Action]:
        # ONLY allow combat on the actual target monster. Falling back to all
        # fights makes the planner happily grind chickens forever while the
        # achievement that actually unlocks the bank stays incomplete.
        fight_actions: list[Action] = [
            a for a in actions
            if isinstance(a, FightAction) and (
                self._target_monster is None or a.monster_code == self._target_monster
            )
        ]
        cleanup_actions: list[Action] = [a for a in actions if "cleanup" in a.tags]
        recovery_actions: list[Action] = [a for a in actions if "recovery" in a.tags]
        # Task 6c: the target-monster fight above has no companion swap in
        # this goal's menu, so a suboptimal equipped weapon makes it
        # inapplicable with no way to fix it (Task 6b regression, mirrored
        # here). Self-guarding: inapplicable once the loadout is optimal.
        swap_actions: list[Action] = []
        if fight_actions and self._target_monster is not None:
            swap_actions.append(OptimizeLoadoutAction(
                target_monster_code=self._target_monster, game_data=game_data))
        return fight_actions + swap_actions + cleanup_actions + recovery_actions

    def _target_monster_is_unreachable(self, state: WorldState, game_data: GameData) -> bool:
        """True when the target monster is over-level enough that combat is hopeless."""
        if not self._target_monster:
            return False
        target_level = game_data.monster_level(self._target_monster)
        if target_level <= 0:
            return False  # unknown monster level — let planner try and fail
        # FightAction.is_applicable already requires level >= monster_level - 1;
        # mirror that so we don't fire when the planner will return [] anyway.
        return state.level < target_level - 1

    def __repr__(self) -> str:
        return f"UnlockBank({self._target_monster or '?'})"

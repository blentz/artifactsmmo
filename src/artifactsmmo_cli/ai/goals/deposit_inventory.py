"""DepositInventoryGoal: deposit bankable inventory to the bank as it fills up."""

import dataclasses

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.bank_selection import select_bank_deposits
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

MIN_FREE_SLOTS = 5


class DepositInventoryGoal(Goal):
    """Deposit bankable inventory to the bank as it fills up.

    Value ramps from the high watermark (85% used → 0) to 100% used (80).
    Satisfied when nothing remains to bank — the keep-set (task item, crafting
    materials, best weapon, task coins, HP consumables, AND the active goal's
    profile materials) may itself exceed any fixed fraction of the bag, so a
    percentage-based satisfaction rule could never be reached.

    SPACE-DRIVEN (spec 2026-06-07): the ramp starts at the high watermark
    (0.85), not 0.5, so the player can use most of its inventory before deposit
    pressure appears. Deposit NEVER banks a profile item — the active gather
    goal's target materials join the keep-set via `profile_codes`. This kills
    the withdraw↔deposit livelock (an active-goal material being banked the
    cycle after it was withdrawn).
    """

    _RAMP_START = 0.85  # fraction used below which the goal is inactive
    _MAX_VALUE = 80.0   # value at 100% used; outranks FarmItems(35) once near cap

    def __init__(self, bank_accessible: bool = True, game_data: GameData | None = None,
                 profile_codes: frozenset[str] = frozenset()) -> None:
        self._bank_accessible = bank_accessible
        self._game_data = game_data
        self._profile_codes = profile_codes

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if not self._bank_accessible or state.inventory_max == 0:
            return 0.0
        if self.is_satisfied(state):
            return 0.0
        used_fraction = state.inventory_used / state.inventory_max
        if used_fraction < self._RAMP_START:
            return 0.0
        # Linear ramp from _RAMP_START → 1.0 mapped onto 0 → _MAX_VALUE.
        return (used_fraction - self._RAMP_START) / (1.0 - self._RAMP_START) * self._MAX_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        if state.inventory_max == 0 or self._game_data is None:
            return True
        # Satisfied once nothing remains to bank (see class docstring).
        return not select_bank_deposits(state, self._game_data, self._profile_codes)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        # Post-deposit inventory_used (current minus everything bankable) — this
        # is exactly the satisfied state, keeping the A* heuristic reachable.
        bankable = (
            sum(qty for _, qty in select_bank_deposits(state, self._game_data,
                                                        self._profile_codes))
            if self._game_data is not None else 0
        )
        return {"inventory_used": state.inventory_used - bankable}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Only `deposit`-tagged actions can reduce inventory_used to the
        bankable-removed target. Without this filter the planner explores the
        full action set (Gather/Fight/Craft/Move/…) up to max_depth=15 looking
        for `inventory_used == target`, which empirically blows to ~30k nodes
        and times out at the 90s budget (trace 2026-06-04 cycles 760/20/60).
        DepositAllAction already includes the Move-to-bank in its apply, so
        movement isn't needed as a separate planner step.

        Deposit actions are re-parameterized with this goal's profile_codes so
        the EXECUTED keep-set matches the one the goal planned with. Run-5
        trace 2026-06-11 23:05 (cycle 10): the factory-built DepositAll had no
        profile and banked the active grind chain's 59 ash_wood."""
        result: list[Action] = []
        for a in actions:
            if "deposit" not in a.tags:
                continue
            if isinstance(a, DepositAllAction):
                a = dataclasses.replace(a, profile_codes=self._profile_codes)
            result.append(a)
        return result

    def __repr__(self) -> str:
        return "DepositInventory"

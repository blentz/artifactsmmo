"""DepositInventoryGoal: deposit bankable inventory to the bank as it fills up."""

import dataclasses

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.bank_selection import select_bank_deposits
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.thresholds import PRESSURE_HIGH_FRACTION
from artifactsmmo_cli.ai.tiers.guards import _used_fraction
from artifactsmmo_cli.ai.world_state import WorldState

MIN_FREE_SLOTS = 5


class DepositInventoryGoal(Goal):
    """Deposit bankable inventory to the bank as it fills up.

    Value ramps from the high watermark (85% used → 0) to 100% used (80).
    Satisfied when nothing remains to bank — the keep CAPS (task item, crafting
    materials, best weapon, task coins, HP consumables, AND the active goal's
    profile materials) may themselves exceed any fixed fraction of the bag, so a
    percentage-based satisfaction rule could never be reached.

    SPACE-DRIVEN (spec 2026-06-07): the ramp starts at the high watermark
    (0.85), not 0.5, so the player can use most of its inventory before deposit
    pressure appears. Deposit never banks a profile item BELOW ITS DEMAND — the
    active gather goal's target materials are the GOAL_MATERIALS keep reason,
    read from `ctx.step_profile`. This kills the withdraw↔deposit livelock (an
    active-goal material being banked the cycle after it was withdrawn) without
    pinning the whole growing pile in the bag.
    """

    _RAMP_START = PRESSURE_HIGH_FRACTION  # fraction used below which the goal is inactive
    _MAX_VALUE = 80.0   # value at 100% used; outranks FarmItems(35) once near cap

    def __init__(self, bank_accessible: bool = True, game_data: GameData | None = None,
                 ctx: SelectionContext = NO_PROFILE_CONTEXT) -> None:
        self._bank_accessible = bank_accessible
        self._game_data = game_data
        self._ctx = ctx

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if not self._bank_accessible or state.inventory_max == 0:
            return 0.0
        if self.is_satisfied(state):
            return 0.0
        # ONE SPACE-PRESSURE FRACTION, AND THE GUARD OWNS IT. `_used_fraction`
        # is `max(QUANTITY fraction, SLOT fraction)` — the same call
        # `_fires(DEPOSIT_FULL)` makes — so the guard can no longer fire on a
        # goal that reports zero. It used to: the guard read the max while this
        # method read the quantity fraction alone, patched with a BINARY
        # `slots_free == 0 -> 1.0` override, so 18 singleton stacks in a
        # 20-slot / 124-quantity bag were 0.90 of the SLOTS (guard fires) and
        # 0.145 of the quantity with two slots still free (value 0.0). Measured
        # 2026-08-25 over the 42 scenarios x 7 bag shapes: 82 of 294 cells, and
        # end to end the arbiter SELECTED `DepositInventory`/`DepositAll` at
        # `goal_rank` 0.0 — which both TUI consumers of that panel filter away
        # (`priority > 0`, strategy_driver.py:820).
        #
        # `Formal.Liveness.MeansFiring._fires_depositFull_implies_depositInventory_positive`
        # proves `fires(DEPOSIT_FULL) => value > 0` over ONE `usedFractionRat`;
        # production had two, which is precisely why a proved lemma did not
        # bind. Sharing the guard's function is what makes the model's single
        # fraction true of the code. The old override is SUBSUMED, not dropped:
        # `slots_free == 0` makes the slot fraction exactly 1.0, so the max is
        # 1.0 — the same top-of-ramp value, now reached by the general rule.
        # `depositInventoryValue` (formal/Formal/GoalSystem.lean) proves this
        # EXACT ramp formula for every `usedFraction` in `[0, 1]`, so no Lean
        # mirror changes.
        used_fraction = _used_fraction(state)
        if used_fraction < self._RAMP_START:
            return 0.0
        # Linear ramp from _RAMP_START → 1.0 mapped onto 0 → _MAX_VALUE.
        return (used_fraction - self._RAMP_START) / (1.0 - self._RAMP_START) * self._MAX_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        if state.inventory_max == 0 or self._game_data is None:
            return True
        # Satisfied once nothing remains to bank (see class docstring).
        return not select_bank_deposits(state, self._game_data, self._ctx)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        # Post-deposit inventory_used (current minus everything bankable) — this
        # is exactly the satisfied state, keeping the A* heuristic reachable.
        surplus = (
            sum(qty for _, qty in select_bank_deposits(state, self._game_data, self._ctx))
            if self._game_data is not None else 0
        )
        return {"inventory_used": state.inventory_used - surplus}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Only `deposit`-tagged actions can reduce inventory_used to the
        bankable-removed target. Without this filter the planner explores the
        full action set (Gather/Fight/Craft/Move/…) up to max_depth=15 looking
        for `inventory_used == target`, which empirically blows to ~30k nodes
        and times out at the 90s budget (trace 2026-06-04 cycles 760/20/60).
        DepositAllAction already includes the Move-to-bank in its apply, so
        movement isn't needed as a separate planner step.

        Deposit actions are re-parameterized with this goal's ctx so the EXECUTED
        keep caps match the ones the goal planned with. Run-5 trace 2026-06-11
        23:05 (cycle 10): the factory-built DepositAll had no profile and banked
        the active grind chain's 59 ash_wood."""
        result: list[Action] = []
        for a in actions:
            if "deposit" not in a.tags:
                continue
            if isinstance(a, DepositAllAction):
                a = dataclasses.replace(a, ctx=self._ctx)
            result.append(a)
        return result

    def __repr__(self) -> str:
        return "DepositInventory"

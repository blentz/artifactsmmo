"""RecycleSurplusGoal: recover materials from surplus craftable gear during idle time."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.recycle_surplus import recyclable_surplus
from artifactsmmo_cli.ai.world_state import WorldState

RECYCLE_SURPLUS_VALUE = 20.0
"""Discretionary housekeeping value: below GATHER_MATERIALS (50) so it never
preempts objective gear/material work, above the WAIT last-resort. Fires during
idle, low-pressure cycles to reclaim materials before surplus gear would pile up
and be DELETED under space pressure (the copper_helmet×9 discard, trace
2026-06-14 122022)."""


class RecycleSurplusGoal(Goal):
    """Recycle surplus craftable equipment to recover its materials.

    Targets gear held above its useful keep-cap that is NOT the committed
    objective (recycling the boots you're building would be self-defeating).
    Recovered materials flow to the bank / the gear chain. See
    `ai/recycle_surplus.recyclable_surplus` for the eligibility rule.
    """

    def __init__(self, game_data: GameData, protected_codes: frozenset[str],
                 gear_keep: dict[str, int] | None = None) -> None:
        self._gd = game_data
        self._protected = protected_codes
        # Active-profile gear-demand keep map (spec
        # 2026-06-28-gear-loadout-profiles): rerouted the equippable cap so
        # un-profiled, not-in-flight gear is reclaimable. None = legacy cap.
        self._gear_keep = gear_keep

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return RECYCLE_SURPLUS_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        return not recyclable_surplus(state, self._gd, self._protected,
                                      gear_keep=self._gear_keep)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"surplus_gear_recycled": True}

    def relevant_actions(
        self, actions: list[Action], state: WorldState, game_data: GameData,
    ) -> list[Action]:
        """One batch RecycleAction per surplus code, sized to fit free space.

        Recycling MINTS recovered materials into the bag, so the quantity is
        capped at what `RecycleAction.is_applicable` accepts given current free
        slots (server HTTP 497). The remainder is reclaimed on a later idle
        cycle once the recovered materials are deposited.
        """
        surplus = recyclable_surplus(state, game_data, self._protected,
                                     gear_keep=self._gear_keep)
        result: list[Action] = []
        for code, surplus_qty in surplus.items():
            # recyclable_surplus guarantees a non-None stats with a crafting
            # skill and a known workshop for every returned code.
            stats = game_data.item_stats(code)
            assert stats is not None and stats.crafting_skill is not None
            workshop = game_data.workshop_location(stats.crafting_skill)
            for qty in range(surplus_qty, 0, -1):
                action = RecycleAction(code=code, quantity=qty, workshop_location=workshop)
                if action.is_applicable(state, game_data):
                    result.append(action)
                    break
        return result

    def __repr__(self) -> str:
        return "RecycleSurplus"

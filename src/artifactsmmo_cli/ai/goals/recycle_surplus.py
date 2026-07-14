"""RecycleSurplusGoal: recover materials from surplus craftable gear during idle time."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.inventory_keep import keep_owned
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.recycle_surplus import recyclable_surplus, recycle_urgency
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

RECYCLE_SURPLUS_VALUE = 20.0
"""Discretionary housekeeping value: below GATHER_MATERIALS (50) so it never
preempts objective gear/material work, above the WAIT last-resort. Fires during
idle, low-pressure cycles to reclaim materials before surplus gear would pile up
and be DELETED under space pressure (the copper_helmet×9 discard, trace
2026-06-14 122022).

value() scales by `recycle_urgency` (every 5 surplus copies of the largest pile
add 1x — a ~40 hoard is 8x). Band position, not value(), drives selection; the
selection-visible half of the same urgency is the arbiter's COLLECT-band hoist
at RECYCLE_HOIST_URGENCY (strategy_driver._build_candidates)."""


class RecycleSurplusGoal(Goal):
    """Recycle surplus craftable equipment to recover its materials.

    Targets the BAG copies the keep authority licenses for destruction — gear
    held above BOTH `keep_in_bag` and `keep_owned` (so the equipped copy, the
    active profile's demand, the working tool and the committed recipe's inputs
    all survive: recycling the boots you're building would be self-defeating).
    Recovered materials flow to the bank / the gear chain. See
    `ai/recycle_surplus.recyclable_surplus` for the eligibility rule.
    """

    def __init__(self, game_data: GameData, ctx: SelectionContext,
                 initial_total: int | None = None) -> None:
        self._gd = game_data
        # The per-cycle SelectionContext the keep authority reads (gear_keep,
        # step_profile). It REPLACES the old `protected_codes` frozenset + the
        # `gear_keep` map: protection is a QUANTITY the authority owns, not a
        # code-set this goal carries (item-protection-authority epic, Task 7).
        self._ctx = ctx
        # Construction-time surplus snapshot: ANY reduction below it satisfies,
        # so a bag-space-capped Recycle batch is a complete 1-action plan and a
        # big hoard melts one batch per cycle. All-or-nothing satisfaction
        # dead-ended the planner (live 2026-07-05: 39 surplus, Recycle x14 was
        # the space cap, plan_len=0 — the hoist selected a goal it could never
        # plan). None keeps the strict all-clear semantics.
        self._initial_total = initial_total

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        surplus = recyclable_surplus(state, self._gd, self._ctx)
        if not surplus:
            return 0.0
        return RECYCLE_SURPLUS_VALUE * recycle_urgency(surplus)

    def is_satisfied(self, state: WorldState) -> bool:
        surplus = recyclable_surplus(state, self._gd, self._ctx)
        if not surplus:
            return True
        return (self._initial_total is not None
                and sum(surplus.values()) < self._initial_total)

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

        These are BATCH actions built OUTSIDE `destructive_license` (the licence
        filters the shared pool's quantity=1 arms; this goal sizes its own), so
        the per-application `owned_floor` must be stamped HERE too or the plan
        can apply the batch more than once and destroy past `destroyable`
        (whole-branch review, CRITICAL 1). The floor is the SAME authority the
        surplus came from: `recyclable_surplus` is `min(bankable, destroyable)`,
        and `destroyable == owned - keep_owned`, so any `qty <= surplus_qty`
        leaves `owned - qty >= keep_owned` — the first application always passes
        its own floor, and a SECOND one cannot.
        """
        surplus = recyclable_surplus(state, game_data, self._ctx)
        result: list[Action] = []
        for code, surplus_qty in surplus.items():
            # recyclable_surplus guarantees a non-None stats with a crafting
            # skill and a known workshop for every returned code.
            stats = game_data.item_stats(code)
            assert stats is not None and stats.crafting_skill is not None
            workshop = game_data.workshop_location(stats.crafting_skill)
            floor = keep_owned(code, state, game_data, self._ctx)
            for qty in range(surplus_qty, 0, -1):
                action = RecycleAction(code=code, quantity=qty, workshop_location=workshop,
                                       owned_floor=floor)
                if action.is_applicable(state, game_data):
                    result.append(action)
                    break
        return result

    def __repr__(self) -> str:
        return "RecycleSurplus"

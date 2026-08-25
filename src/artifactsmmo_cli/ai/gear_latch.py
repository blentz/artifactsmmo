"""Latch that prioritizes the gear chain while gear is what stands in the way.

Two arms, deliberately not the same shape:

  * EDGE — a level-up or a predicted-winnable fight loss. A moment, so it latches
    and holds until no craftable upgrade remains for any slot.
  * STANDING — a held task whose monster is unwinnable, GEAR IS WHAT CLOSES IT
    (`task_horizon.HORIZON_GEAR`), and no other monster is worth fighting. A
    condition, so it is recomputed every cycle and releases on its own the moment
    any part stops holding.

Owned by the player and updated once per cycle BEFORE goal selection; read via
`active` to fire the GEAR_REVIEW guard. See the tiered-budget spec."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_appropriateness import has_craftable_upgrade_any_slot
from artifactsmmo_cli.ai.task_horizon import HORIZON_GEAR, resolve_task_horizon
from artifactsmmo_cli.ai.world_state import WorldState


class GearLatch:
    """Boolean latch. SET on level-up or `error:fight_lost` (holding until no
    craftable upgrade remains for any slot), and additionally ACTIVE for as long
    as a held task's monster is unwinnable, a gear chain CLOSES that fight, and
    nothing else is worth fighting."""

    def __init__(self) -> None:
        self._active = False
        self._blocked = False

    @property
    def active(self) -> bool:
        return self._active or self._blocked

    def update(self, prev_level: int, state: WorldState, last_outcome: str | None,
               game_data: GameData, winnable_alternative: bool) -> None:
        """Re-evaluate the latch for this cycle.

        Args:
          prev_level:           character level on the previous cycle.
          last_outcome:         outcome string of the previously executed action
                                (None on the first cycle).
          winnable_alternative: whether the cascade found a monster worth farming
                                this cycle (`_winnable_farm_target() is not None`).
        """
        # A DEFICIT THAT EXISTS is a reason to review gear, whether or not we
        # just walked into it. The latch used to arm only on an EVENT — a loss
        # this cycle — and closing the tier-1 bypass stopped the bot taking
        # fights it loses, which removed the very trigger the CURE depended on.
        # Measured live 40 minutes after that shipped: C3P0 held an unwinnable
        # pig task with `gear: {"adequate": false}`, a deficit target available
        # and a craftable upgrade available, and still went four consecutive
        # cycles of `Wait` with an EMPTY goal_rank, because nothing had armed it.
        # Same error class as the countdown this epic replaced, one layer up.
        if state.level > prev_level or last_outcome == "error:fight_lost":
            self._active = True
        craftable = has_craftable_upgrade_any_slot(state, game_data)
        if self._active and not craftable:
            self._active = False
        # ...but a deficit only BLOCKS when there is nothing else to fight, and
        # that is the condition C3P0's four `Wait` cycles actually exhibited.
        # Shipped gated on the deficit alone — strictly broader — and the
        # difference is not academic: GEAR_REVIEW is a GUARD, so it preempts the
        # objective step outright (`arbiter_select.select_pure` returns the first
        # candidate that plans, and the guard's goal always plans).
        #
        # Live R2D2 2026-08-21/22: held `monsters/pig 0/137` at combat_margin -2
        # for 38 hours. The deficit was real, so the latch re-armed every cycle,
        # so GEAR_REVIEW preempted `GrindCharacterXP(skeleton)` — winnable, 37
        # xp/kill — for 981 consecutive cycles. Character XP frozen 31.6 hours at
        # 1861/8200. No level-up and no `error:fight_lost` occurred in that whole
        # run, so the EDGE arm was never set and this was the sole cause.
        #
        # USER (2026-08-22): "not being able to win against a pig is fine. but
        # that shouldn't block us from fighting other, winnable monsters."
        #
        # STANDING, not latched: a frozen character has no edge left to re-trigger
        # it, so an arm that only stopped RE-arming would need a restart to take
        # effect. Releasing on its own is what unfreezes one mid-run.
        #
        # ...AND ONLY WHEN GEAR IS WHAT STANDS IN THE WAY, which is this class's
        # whole contract (see the module docstring) and was NOT what it checked.
        # `has_combat_deficit` is the BARE FACT "this fight is lost", so the latch
        # armed identically whether the catalogue held a chain that wins the fight
        # or held nothing that could. In the second case GEAR_REVIEW preempts the
        # objective step to build gear that provably cannot close the gap — measured
        # over the offline corpus after `e6a2e37c`, the "nothing closes it" side is
        # the MAJORITY of losing pairs, and it is the side that falls through to the
        # monster-blind value scan (`iron_boots`, ten hours).
        #
        # `HORIZON_LEVEL_UP` deliberately does NOT arm it either. The standing arm's
        # other conjunct is `not winnable_alternative` — no monster worth fighting —
        # so a level-up verdict reached here has nothing to fight for the level, and
        # `map_guard`'s LEVEL_UP arm would map to a goal with no beatable monster in
        # its `relevant_actions`. That verdict is served from the EDGE arm (a real
        # loss or level-up, where the cascade does find something), and served here
        # by the latch STAYING OFF so the objective's own XP grind runs.
        #
        # WHAT THE VERDICT COSTS, since `update` runs EVERY cycle for every
        # character and the fleet's binding constraint is a per-IP rate budget.
        # Measured 2026-08-25 on the scenario bundle, median of 20, over the six
        # task-holding cells — the guard `craftable and not winnable_alternative`
        # is unchanged, so this compares like for like against the
        # `has_combat_deficit` call it replaced:
        #
        #   old (has_combat_deficit, one predict_win)      0.018 ms
        #   new, no deficit (early-out on the same call)   0.019 ms
        #   new, a verdict to reach          1.3 - 5.4 ms  (2.0 ms mean)
        #   new, `per_state` memo hit                      0.0001 ms
        #
        # The 5.4 ms worst case is the OUT_OF_REACH arm, which is the only one
        # that walks the catalogue twice (once at this level, once at level+1).
        # Against the live mean cycle of 28.95 s (84,590 cycles in
        # `learning.db`) that is 0.019 % of one cycle, and the memo means the
        # guard mapper and the cancel rung then pay nothing. Not a finding —
        # recorded so the next edit to this arm has a baseline to beat.
        horizon = (resolve_task_horizon(state, game_data)
                   if craftable and not winnable_alternative else None)
        self._blocked = horizon is not None and horizon.verdict == HORIZON_GEAR

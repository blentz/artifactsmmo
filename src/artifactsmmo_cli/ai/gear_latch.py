"""Latch that prioritizes the gear chain while gear is what stands in the way.

Two arms, deliberately not the same shape:

  * EDGE — a level-up or a predicted-winnable fight loss. A moment, so it latches
    and holds until no craftable upgrade remains for any slot.
  * STANDING — a held task whose monster is unwinnable AND no other monster worth
    fighting. A condition, so it is recomputed every cycle and releases on its
    own the moment either half stops holding.

Owned by the player and updated once per cycle BEFORE goal selection; read via
`active` to fire the GEAR_REVIEW guard. See the tiered-budget spec."""

from artifactsmmo_cli.ai.combat_deficit import has_combat_deficit
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_appropriateness import has_craftable_upgrade_any_slot
from artifactsmmo_cli.ai.world_state import WorldState


class GearLatch:
    """Boolean latch. SET on level-up or `error:fight_lost` (holding until no
    craftable upgrade remains for any slot), and additionally ACTIVE for as long
    as a held task's monster is unwinnable with nothing else worth fighting."""

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
        self._blocked = (craftable and not winnable_alternative
                         and has_combat_deficit(state, game_data))

"""The gear-review EDGE: a level-up or a predicted-winnable fight loss.

ONE ARM, since wave 4. It had two, and the other one — STANDING, a held task
whose monster is unwinnable and which gear closes — is now
`decisions/root.IsAFightBlockingMe`. That move is the point of the wave: a
standing condition expressed as a latch froze R2D2's character XP for 981
consecutive cycles, and a `Decision` is rebuilt every cycle so it cannot latch
at all.

The edge is a MOMENT, so latching is the right shape for it: it holds until no
craftable upgrade remains for any slot.

Two readers, deliberately different:

  * `active` — the raw edge, for plan-cache invalidation (`should_replan.py:30`).
  * `level_up_pending` — the edge AND a `HORIZON_LEVEL_UP` verdict, which fires
    the GEAR_REVIEW guard. The guard's one surviving arm maps that verdict and
    nothing else, so the flag has to be exactly that narrow.

Owned by the player and updated once per cycle BEFORE goal selection."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_appropriateness import has_craftable_upgrade_any_slot
from artifactsmmo_cli.ai.task_horizon import HORIZON_LEVEL_UP, resolve_task_horizon
from artifactsmmo_cli.ai.world_state import WorldState


class RegearEdge:
    """Boolean latch. SET on level-up or `error:fight_lost` (holding until no
    craftable upgrade remains for any slot), and additionally ACTIVE for as long
    as a held task's monster is unwinnable, a gear chain CLOSES that fight, and
    nothing else is worth fighting."""

    def __init__(self) -> None:
        self._active = False
        self._level_up_pending = False

    @property
    def active(self) -> bool:
        """The EDGE, for plan-cache invalidation (`should_replan.py:30`).

        `_blocked` — the standing arm — left this class in wave 4 and is now
        `decisions/root.IsAFightBlockingMe`, a node with no memory. What remains
        is the edge, which is the only part `should_replan` ever wanted: it
        compares this flag against the cached one, so it is an edge detector on
        an edge fact.
        """
        return self._active

    @property
    def level_up_pending(self) -> bool:
        """Edge armed AND the held fight is one level away — the guard's flag.

        The guard's surviving arm maps only `HORIZON_LEVEL_UP`, so the firing
        condition has to be exactly that. A bare `self._active` would fire a
        guard whose only arm cannot answer, on every edge with a GEAR, None or
        out-of-reach verdict.

        A STICKY FLAG DRIVING GOAL SELECTION IS THE 981-CYCLE FREEZE, so the
        convergence argument has to be explicit. `_active` does hold across
        cycles (it clears only when no craftable upgrade remains). It is safe
        here because the goal it maps to is `ReachUnlockLevelGoal(level + 1)`:
        reaching that level re-reads the horizon, which then answers GEAR, None,
        or a further LEVEL_UP. Every iteration buys a real level, so this makes
        progress by construction. The freeze was the opposite — zero progress at
        a fixed level, forever.
        """
        return self._level_up_pending

    def update(self, prev_level: int, state: WorldState, last_outcome: str | None,
               game_data: GameData) -> None:
        """Re-evaluate the latch for this cycle.

        Args:
          prev_level:           character level on the previous cycle.
          last_outcome:         outcome string of the previously executed action
                                (None on the first cycle).
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
        # THE STANDING ARM LEFT THIS CLASS (wave 4). What stood here computed
        # `_blocked` from `HORIZON_GEAR` and `not winnable_alternative` and fed
        # the GEAR_REVIEW guard — and a guard preempts the objective step
        # outright. Live R2D2 2026-08-21/22 held `monsters/pig 0/137` at
        # combat_margin -2 for 38 hours: the deficit was real, so the latch
        # re-armed every cycle, so GEAR_REVIEW preempted `GrindCharacterXP
        # (skeleton)` — winnable, 37 xp/kill — for 981 consecutive cycles, with
        # character XP frozen 31.6 h at 1861/8200. No level-up and no
        # `error:fight_lost` occurred in that whole run, so the EDGE arm was
        # never set and the standing arm was the sole cause.
        #
        # USER (2026-08-22): "not being able to win against a pig is fine. but
        # that shouldn't block us from fighting other, winnable monsters."
        #
        # It is now `decisions/root.IsAFightBlockingMe`, a `Decision` built fresh
        # every cycle. The fix is structural rather than a narrowing: a node
        # cannot latch, so that freeze is no longer representable.
        #
        # WHAT STAYS HERE IS THE EDGE, and one verdict read off it. The horizon
        # is asked whenever the edge is armed and something is craftable — NOT
        # gated on `winnable_alternative` any more, because the level-up arm
        # WANTS the case where the cascade found something to fight: that is the
        # monster the level gets ground on. Costs the 1.3-5.4 ms verdict on
        # armed-edge cycles only, and `resolve_task_horizon` is `per_state`
        # memoised, so the guard mapper and the cancel rung then pay nothing.
        horizon = (resolve_task_horizon(state, game_data)
                   if self._active and craftable else None)
        self._level_up_pending = (horizon is not None
                                  and horizon.verdict == HORIZON_LEVEL_UP)

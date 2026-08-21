"""Latch that prioritizes the gear chain while gear is what stands in the way.

Set by a level-up, a predicted-winnable fight loss, or — the FACT rather than the
event — a held task whose monster is unwinnable. Cleared when no craftable
upgrade remains for any slot. Owned by the player and updated
once per cycle BEFORE goal selection; read via `active` to fire the GEAR_REVIEW
guard. See the tiered-budget spec."""

from artifactsmmo_cli.ai.combat_deficit import has_combat_deficit
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_appropriateness import has_craftable_upgrade_any_slot
from artifactsmmo_cli.ai.world_state import WorldState


class GearLatch:
    """Boolean latch. SET on level-up, on `error:fight_lost`, or while a held
    task's monster is unwinnable; CLEAR when no craftable upgrade remains for any
    slot; otherwise holds its prior value."""

    def __init__(self) -> None:
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def update(self, prev_level: int, state: WorldState, last_outcome: str | None,
               game_data: GameData) -> None:
        """Re-evaluate the latch for this cycle. `prev_level` is the character
        level from the previous cycle; `last_outcome` is the outcome string of the
        previously executed action (None on the first cycle)."""
        # A DEFICIT THAT EXISTS is a reason to review gear, whether or not we
        # just walked into it. The latch used to arm only on an EVENT — a loss
        # this cycle — and closing the tier-1 bypass stopped the bot taking
        # fights it loses, which removed the very trigger the CURE depended on.
        # Measured live 40 minutes after that shipped: C3P0 held an unwinnable
        # pig task with `gear: {"adequate": false}`, a deficit target available
        # and a craftable upgrade available, and still went four consecutive
        # cycles of `Wait` with an EMPTY goal_rank, because nothing had armed it.
        # Same error class as the countdown this epic replaced, one layer up.
        triggered = (state.level > prev_level
                     or last_outcome == "error:fight_lost"
                     or has_combat_deficit(state, game_data))
        if triggered:
            self._active = True
        if self._active and not has_craftable_upgrade_any_slot(state, game_data):
            self._active = False

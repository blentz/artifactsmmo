"""Latch that prioritizes the gear chain after a level-up or a predicted-winnable
fight loss, until equipment is level-appropriate. Owned by the player and updated
once per cycle BEFORE goal selection; read via `active` to fire the GEAR_REVIEW
guard. See the tiered-budget spec."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_appropriateness import has_craftable_upgrade_any_slot
from artifactsmmo_cli.ai.world_state import WorldState


class GearLatch:
    """Boolean latch. SET on level-up or `error:fight_lost`; CLEAR when no
    craftable upgrade remains for any slot; otherwise holds its prior value."""

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
        triggered = state.level > prev_level or last_outcome == "error:fight_lost"
        if triggered:
            self._active = True
        if self._active and not has_craftable_upgrade_any_slot(state, game_data):
            self._active = False

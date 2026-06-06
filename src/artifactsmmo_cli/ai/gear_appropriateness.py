"""Gear is 'level-appropriate' when no craftable upgrade remains for any slot —
the clear condition for the gear-review latch. Delegates to the proven
UpgradeEquipmentGoal craftable-upgrade selection so this stays the single source
of truth for 'what is an upgrade'."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.world_state import WorldState


def has_craftable_upgrade_any_slot(state: WorldState, game_data: GameData) -> bool:
    """True iff some equippable slot has a better craftable item at the
    character's current level (uncommitted UpgradeEquipment finds one)."""
    probe = UpgradeEquipmentGoal()  # uncommitted ⇒ scans all slots for the best upgrade
    return probe.find_upgrade_target(state, game_data) is not None

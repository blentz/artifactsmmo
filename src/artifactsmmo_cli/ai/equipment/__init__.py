"""Equipment optimization: pick best loadout for a given purpose."""

from artifactsmmo_cli.ai.equipment.elements import ELEMENTS
from artifactsmmo_cli.ai.equipment.scoring import (
    armor_score,
    weapon_score,
)

__all__ = ["ELEMENTS", "armor_score", "weapon_score"]

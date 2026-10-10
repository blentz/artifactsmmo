"""The heal consumables of the API item catalogue, by class: FOOD
(`type_ == "consumable"`, eaten out of combat) and POTION (`type_ ==
"utility"`, worn in a utility slot). Read by the loop rate's food menu, the
best loadout's candidates, and so the fleet floor's need."""

from artifactsmmo_cli.ai.game_data import GameData

FOOD = "consumable"
POTION = "utility"


def heal_candidates(game_data: GameData, type_: str) -> list[str]:
    """Every heal of `type_`, in catalogue order."""
    return [code for code, stats in game_data.items.stats.items()
            if stats.type_ == type_ and stats.hp_restore > 0]

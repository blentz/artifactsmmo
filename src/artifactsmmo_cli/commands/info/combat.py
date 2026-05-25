"""Combat assessment helpers shared by the monster commands."""

from typing import Any

import httpx
from artifactsmmo_api_client.api.characters import get_character_characters_name_get
from artifactsmmo_api_client.errors import UnexpectedStatus

from artifactsmmo_cli.commands import info as _pkg


def _get_character_data(character_name: str) -> dict[str, str | int] | None:
    """Get character data for combat assessment.

    Args:
        character_name: Name of the character to fetch

    Returns:
        Character data dictionary or None if not found
    """
    try:
        client = _pkg.ClientManager().client
        response = get_character_characters_name_get.sync(client=client, name=character_name)
        cli_response = _pkg.handle_api_response(response)

        if cli_response.success and cli_response.data:
            character = cli_response.data
            return {
                "name": getattr(character, "name", ""),
                "level": getattr(character, "level", 0),
                "hp": getattr(character, "hp", 0),
                "max_hp": getattr(character, "max_hp", 0),
                "attack_fire": getattr(character, "attack_fire", 0),
                "attack_earth": getattr(character, "attack_earth", 0),
                "attack_water": getattr(character, "attack_water", 0),
                "attack_air": getattr(character, "attack_air", 0),
                "res_fire": getattr(character, "res_fire", 0),
                "res_earth": getattr(character, "res_earth", 0),
                "res_water": getattr(character, "res_water", 0),
                "res_air": getattr(character, "res_air", 0),
                "dmg": getattr(character, "dmg", 0),
                "dmg_fire": getattr(character, "dmg_fire", 0),
                "dmg_earth": getattr(character, "dmg_earth", 0),
                "dmg_water": getattr(character, "dmg_water", 0),
                "dmg_air": getattr(character, "dmg_air", 0),
            }
    except (UnexpectedStatus, httpx.HTTPError):
        pass

    return None


def _calculate_difficulty_rating(char_level: int, monster_level: int) -> dict[str, str]:
    """Calculate difficulty rating based on level difference.

    Args:
        char_level: Character level
        monster_level: Monster level

    Returns:
        Dictionary with difficulty info (rating, color, emoji)
    """
    level_diff = monster_level - char_level

    if level_diff <= -2:
        return {"rating": "Easy", "color": "green", "emoji": "🟢"}
    elif -1 <= level_diff <= 1:
        return {"rating": "Medium", "color": "yellow", "emoji": "🟡"}
    elif 2 <= level_diff <= 3:
        return {"rating": "Hard", "color": "red", "emoji": "🟠"}
    else:  # level_diff >= 4
        return {"rating": "Deadly", "color": "bright_red", "emoji": "🔴"}


def _calculate_success_probability(character: dict[str, str | int], monster: dict[str, str | int]) -> int:
    """Calculate estimated success probability for combat.

    Args:
        character: Character data dictionary
        monster: Monster data dictionary

    Returns:
        Success probability as percentage (0-100)
    """
    char_level = int(character.get("level", 0))
    monster_level = int(monster.get("level", 0))
    char_hp = int(character.get("max_hp", 0))
    monster_hp = int(monster.get("hp", 0))

    # Base probability from level difference
    level_diff = monster_level - char_level
    if level_diff <= -2:
        base_prob = 90
    elif -1 <= level_diff <= 1:
        base_prob = 75
    elif 2 <= level_diff <= 3:
        base_prob = 50
    else:
        base_prob = 25

    # Adjust for HP difference
    if char_hp > 0 and monster_hp > 0:
        hp_ratio = char_hp / monster_hp
        if hp_ratio > 2.0:
            base_prob += 10
        elif hp_ratio > 1.5:
            base_prob += 5
        elif hp_ratio < 0.5:
            base_prob -= 15
        elif hp_ratio < 0.75:
            base_prob -= 10

    # Calculate total damage potential vs monster HP
    char_total_attack = (
        int(character.get("attack_fire", 0))
        + int(character.get("attack_earth", 0))
        + int(character.get("attack_water", 0))
        + int(character.get("attack_air", 0))
    )

    if char_total_attack > 0 and monster_hp > 0:
        damage_ratio = char_total_attack / monster_hp
        if damage_ratio > 0.5:
            base_prob += 5
        elif damage_ratio < 0.1:
            base_prob -= 10

    # Clamp to reasonable range
    return max(5, min(95, base_prob))


def _format_combat_analysis(character: dict[str, str | int], monster: dict[str, str | int]) -> list[list[str]]:
    """Format combat analysis for display.

    Args:
        character: Character data dictionary
        monster: Monster data dictionary

    Returns:
        List of table rows for combat analysis
    """
    char_level = int(character.get("level", 0))
    monster_level = int(monster.get("level", 0))

    difficulty = _calculate_difficulty_rating(char_level, monster_level)
    success_prob = _calculate_success_probability(character, monster)

    rows = [
        ["Character Level", str(char_level)],
        ["Monster Level", str(monster_level)],
        ["Level Difference", f"{monster_level - char_level:+d}"],
        ["Difficulty", f"{difficulty['emoji']} {difficulty['rating']}"],
        ["Success Probability", f"{success_prob}%"],
    ]

    # HP comparison
    char_hp = int(character.get("max_hp", 0))
    monster_hp = int(monster.get("hp", 0))
    rows.extend(
        [
            ["Character HP", str(char_hp)],
            ["Monster HP", str(monster_hp)],
        ]
    )

    # Damage comparison
    char_total_attack = (
        int(character.get("attack_fire", 0))
        + int(character.get("attack_earth", 0))
        + int(character.get("attack_water", 0))
        + int(character.get("attack_air", 0))
    )
    monster_total_attack = (
        int(monster.get("attack_fire", 0))
        + int(monster.get("attack_earth", 0))
        + int(monster.get("attack_water", 0))
        + int(monster.get("attack_air", 0))
    )

    rows.extend(
        [
            ["Character Total Attack", str(char_total_attack)],
            ["Monster Total Attack", str(monster_total_attack)],
        ]
    )

    # Recommended level
    if difficulty["rating"] in ["Hard", "Deadly"]:
        recommended_level = monster_level - 1
        rows.append(["Recommended Level", f"{recommended_level}+"])

    return rows


def _get_monster_drops(monster: Any) -> list[str]:
    """Extract monster drop information.

    Args:
        monster: Monster object from API

    Returns:
        List of drop descriptions
    """
    drops = []
    if hasattr(monster, "drops") and monster.drops:
        for drop in monster.drops:
            drop_code = getattr(drop, "code", "Unknown")
            drop_rate = getattr(drop, "rate", 0)
            min_quantity = getattr(drop, "min_quantity", 1)
            max_quantity = getattr(drop, "max_quantity", 1)

            if min_quantity == max_quantity:
                quantity_str = str(min_quantity)
            else:
                quantity_str = f"{min_quantity}-{max_quantity}"

            drops.append(f"{drop_code} x{quantity_str} ({drop_rate}%)")

    return drops

"""Output formatting utilities for the CLI."""

import json
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def _get_attr_or_key(obj: Any, key: str, default: Any = "") -> Any:
    """Get attribute or dictionary key from object."""
    if hasattr(obj, key):
        return getattr(obj, key, default)
    elif hasattr(obj, "get"):
        return obj.get(key, default)
    else:
        return default


def format_character_table(characters: list[Any]) -> Table:
    """Format character list as a table."""
    table = Table(title="Characters", box=box.ROUNDED)
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Level", justify="right", style="magenta")
    table.add_column("Class", style="green")
    table.add_column("HP", justify="right", style="red")
    table.add_column("MP", justify="right", style="blue")
    table.add_column("Gold", justify="right", style="yellow")
    table.add_column("Location", style="white")

    if not characters:
        table.add_row("[dim]No characters found[/dim]", "", "", "", "", "", "")
        return table

    for char in characters:
        table.add_row(
            str(_get_attr_or_key(char, "name", "")),
            str(_get_attr_or_key(char, "level", 0)),
            str(_get_attr_or_key(char, "class", "None")),
            f"{_get_attr_or_key(char, 'hp', 0)}/{_get_attr_or_key(char, 'max_hp', 0)}",
            f"{_get_attr_or_key(char, 'mp', 0)}/{_get_attr_or_key(char, 'max_mp', 0)}",
            str(_get_attr_or_key(char, "gold", 0)),
            f"({_get_attr_or_key(char, 'x', 0)}, {_get_attr_or_key(char, 'y', 0)})",
        )

    return table


def format_item_table(items: list[dict[str, Any]]) -> Table:
    """Format item list as a table."""
    table = Table(title="Items", box=box.ROUNDED)
    table.add_column("Code", style="cyan", no_wrap=True)
    table.add_column("Name", style="white")
    table.add_column("Type", style="green")
    table.add_column("Level", justify="right", style="magenta")
    table.add_column("Quantity", justify="right", style="yellow")

    if not items:
        table.add_row("[dim]No items found[/dim]", "", "", "", "")
        return table

    for item in items:
        table.add_row(
            item.get("code", ""),
            item.get("name", ""),
            item.get("type_", ""),
            str(item.get("level", 0)),
            str(item.get("quantity", 1)),
        )

    return table


def format_bank_table(bank_items: list[dict[str, Any]]) -> Table:
    """Format bank items as a table."""
    table = Table(title="Bank Items", box=box.ROUNDED)
    table.add_column("Code", style="cyan", no_wrap=True)
    table.add_column("Quantity", justify="right", style="yellow")

    if not bank_items:
        table.add_row("[dim]Bank is empty[/dim]", "")
        return table

    for item in bank_items:
        table.add_row(item.get("code", ""), str(item.get("quantity", 0)))

    return table


def format_success_message(message: str) -> Text:
    """Format a success message."""
    return Text(f"✓ {message}", style="bold green")


def format_error_message(message: str) -> Text:
    """Format an error message."""
    return Text(f"✗ {message}", style="bold red")


def format_warning_message(message: str) -> Text:
    """Format a warning message."""
    return Text(f"⚠ {message}", style="bold yellow")


def format_cooldown_message(seconds: int) -> Text:
    """Format a cooldown message with human-readable time."""
    time_str = format_time_duration(seconds)
    return Text(f"⏱ Action on cooldown for {time_str}", style="bold blue")


def format_time_duration(seconds: int) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds} seconds"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        if remaining_seconds == 0:
            return f"{minutes} minutes"
        else:
            return f"{minutes}m {remaining_seconds}s"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        remaining_seconds = seconds % 60

        parts = [f"{hours}h"]
        if remaining_minutes > 0:
            parts.append(f"{remaining_minutes}m")
        if remaining_seconds > 0:
            parts.append(f"{remaining_seconds}s")

        return " ".join(parts)


def format_json_output(data: Any) -> str:
    """Format data as JSON."""
    return json.dumps(data, indent=2, default=str)


def format_table(headers: list[str], rows: list[list[str]], title: str = "") -> Table:
    """Format data as a generic table."""
    table = Table(title=title, box=box.ROUNDED)

    # Add columns
    for header in headers:
        table.add_column(header, style="white")

    # Add rows
    for row in rows:
        table.add_row(*row)

    return table


def format_map_info(map_data: dict[str, Any]) -> str:
    """Format map information."""
    table = Table(title=f"Map ({map_data.get('x', 0)}, {map_data.get('y', 0)})", box=box.ROUNDED)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Name", map_data.get("name", "Unknown"))
    table.add_row("Skin", map_data.get("skin", ""))
    table.add_row("Content Type", map_data.get("content", {}).get("type", ""))
    table.add_row("Content Code", map_data.get("content", {}).get("code", ""))

    with console.capture() as capture:
        console.print(table)
    return capture.get()


def format_combat_result(fight_data: dict[str, Any]) -> Text:
    """Format combat result with detailed information."""
    result_parts = []

    # Basic fight result
    if fight_data.get("result") == "win":
        result_parts.append("🗡️ Victory!")
    elif fight_data.get("result") in ("lose", "loss"):
        result_parts.append("💀 Defeat!")
    else:
        result_parts.append("⚔️ Combat completed")

    # Add damage information if available
    if "damage" in fight_data:
        damage = fight_data["damage"]
        result_parts.append(f"Damage dealt: {damage}")

    # Add XP gained if available
    if "xp" in fight_data:
        xp = fight_data["xp"]
        result_parts.append(f"XP gained: {xp}")

    # Add gold gained if available
    if "gold" in fight_data:
        gold = fight_data["gold"]
        if gold > 0:
            result_parts.append(f"Gold gained: {gold}")

    # Add items dropped if available
    if "drops" in fight_data and fight_data["drops"]:
        drops = fight_data["drops"]
        if isinstance(drops, list) and drops:
            drop_strs = []
            for drop in drops:
                if isinstance(drop, dict):
                    code = drop.get("code", "unknown")
                    quantity = drop.get("quantity", 1)
                    drop_strs.append(f"{quantity}x {code}")
                else:
                    drop_strs.append(str(drop))
            if drop_strs:
                result_parts.append(f"Items dropped: {', '.join(drop_strs)}")

    message = " | ".join(result_parts)

    # Color based on result
    if fight_data.get("result") == "win":
        return Text(message, style="bold green")
    elif fight_data.get("result") in ("lose", "loss"):
        return Text(message, style="bold red")
    else:
        return Text(message, style="bold yellow")


def format_gathering_result(gather_data: dict[str, Any]) -> Text:
    """Format gathering result with detailed information."""
    result_parts = []

    # Basic gathering result
    result_parts.append("🌿 Gathering completed")

    # Add XP gained if available
    if "xp" in gather_data:
        xp = gather_data["xp"]
        result_parts.append(f"XP gained: {xp}")

    # Add items gathered if available
    if "items" in gather_data and gather_data["items"]:
        items = gather_data["items"]
        if isinstance(items, list) and items:
            item_strs = []
            for item in items:
                if isinstance(item, dict):
                    code = item.get("code", "unknown")
                    quantity = item.get("quantity", 1)
                    item_strs.append(f"{quantity}x {code}")
                else:
                    item_strs.append(str(item))
            if item_strs:
                result_parts.append(f"Items gathered: {', '.join(item_strs)}")

    message = " | ".join(result_parts)
    return Text(message, style="bold green")


def format_character_status(character: Any) -> Panel:
    """Format detailed character status with skills and combat stats."""
    from rich.columns import Columns

    # Basic character info
    basic_info = Table(box=box.ROUNDED, title="Character Info")
    basic_info.add_column("Property", style="cyan")
    basic_info.add_column("Value", style="white")

    basic_info.add_row("Name", str(_get_attr_or_key(character, "name", "N/A")))
    basic_info.add_row("Level", str(_get_attr_or_key(character, "level", 0)))
    basic_info.add_row("Class", str(_get_attr_or_key(character, "class", "None")))
    basic_info.add_row("XP", f"{_get_attr_or_key(character, 'xp', 0)}/{_get_attr_or_key(character, 'max_xp', 0)}")
    basic_info.add_row("Gold", str(_get_attr_or_key(character, "gold", 0)))
    basic_info.add_row("HP", f"{_get_attr_or_key(character, 'hp', 0)}/{_get_attr_or_key(character, 'max_hp', 0)}")
    basic_info.add_row("MP", f"{_get_attr_or_key(character, 'mp', 0)}/{_get_attr_or_key(character, 'max_mp', 0)}")
    basic_info.add_row("Position", f"({_get_attr_or_key(character, 'x', 0)}, {_get_attr_or_key(character, 'y', 0)})")
    basic_info.add_row("Cooldown", str(_get_attr_or_key(character, "cooldown", 0)) + " seconds")
    basic_info.add_row("Cooldown Expiration", str(_get_attr_or_key(character, "cooldown_expiration", "N/A")))

    # Gathering skills
    gathering_skills = Table(box=box.ROUNDED, title="Gathering Skills")
    gathering_skills.add_column("Skill", style="green")
    gathering_skills.add_column("Level", justify="right", style="cyan")
    gathering_skills.add_column("XP", justify="right", style="yellow")

    gathering_skills.add_row(
        "Mining",
        str(_get_attr_or_key(character, "mining_level", 0)),
        f"{_get_attr_or_key(character, 'mining_xp', 0)}/{_get_attr_or_key(character, 'mining_max_xp', 0)}",
    )
    gathering_skills.add_row(
        "Woodcutting",
        str(_get_attr_or_key(character, "woodcutting_level", 0)),
        f"{_get_attr_or_key(character, 'woodcutting_xp', 0)}/{_get_attr_or_key(character, 'woodcutting_max_xp', 0)}",
    )
    gathering_skills.add_row(
        "Fishing",
        str(_get_attr_or_key(character, "fishing_level", 0)),
        f"{_get_attr_or_key(character, 'fishing_xp', 0)}/{_get_attr_or_key(character, 'fishing_max_xp', 0)}",
    )

    # Crafting skills
    crafting_skills = Table(box=box.ROUNDED, title="Crafting Skills")
    crafting_skills.add_column("Skill", style="magenta")
    crafting_skills.add_column("Level", justify="right", style="cyan")
    crafting_skills.add_column("XP", justify="right", style="yellow")

    crafting_skills.add_row(
        "Weaponcrafting",
        str(_get_attr_or_key(character, "weaponcrafting_level", 0)),
        f"{_get_attr_or_key(character, 'weaponcrafting_xp', 0)}/"
        f"{_get_attr_or_key(character, 'weaponcrafting_max_xp', 0)}",
    )
    crafting_skills.add_row(
        "Gearcrafting",
        str(_get_attr_or_key(character, "gearcrafting_level", 0)),
        f"{_get_attr_or_key(character, 'gearcrafting_xp', 0)}/{_get_attr_or_key(character, 'gearcrafting_max_xp', 0)}",
    )
    crafting_skills.add_row(
        "Jewelrycrafting",
        str(_get_attr_or_key(character, "jewelrycrafting_level", 0)),
        f"{_get_attr_or_key(character, 'jewelrycrafting_xp', 0)}/"
        f"{_get_attr_or_key(character, 'jewelrycrafting_max_xp', 0)}",
    )
    crafting_skills.add_row(
        "Cooking",
        str(_get_attr_or_key(character, "cooking_level", 0)),
        f"{_get_attr_or_key(character, 'cooking_xp', 0)}/{_get_attr_or_key(character, 'cooking_max_xp', 0)}",
    )
    crafting_skills.add_row(
        "Alchemy",
        str(_get_attr_or_key(character, "alchemy_level", 0)),
        f"{_get_attr_or_key(character, 'alchemy_xp', 0)}/{_get_attr_or_key(character, 'alchemy_max_xp', 0)}",
    )

    # Combat stats
    combat_stats = Table(box=box.ROUNDED, title="Combat Stats")
    combat_stats.add_column("Stat", style="red")
    combat_stats.add_column("Value", justify="right", style="white")

    combat_stats.add_row("Haste", str(_get_attr_or_key(character, "haste", 0)))
    combat_stats.add_row("Critical Strike", f"{_get_attr_or_key(character, 'critical_strike', 0)}%")
    combat_stats.add_row("Wisdom", str(_get_attr_or_key(character, "wisdom", 0)))
    combat_stats.add_row("Prospecting", str(_get_attr_or_key(character, "prospecting", 0)))

    # Attack stats
    attack_stats = Table(box=box.ROUNDED, title="Attack Stats")
    attack_stats.add_column("Element", style="red")
    attack_stats.add_column("Attack", justify="right", style="white")
    attack_stats.add_column("Damage %", justify="right", style="yellow")

    attack_stats.add_row(
        "Fire", str(_get_attr_or_key(character, "attack_fire", 0)), f"{_get_attr_or_key(character, 'dmg_fire', 0)}%"
    )
    attack_stats.add_row(
        "Earth", str(_get_attr_or_key(character, "attack_earth", 0)), f"{_get_attr_or_key(character, 'dmg_earth', 0)}%"
    )
    attack_stats.add_row(
        "Water", str(_get_attr_or_key(character, "attack_water", 0)), f"{_get_attr_or_key(character, 'dmg_water', 0)}%"
    )
    attack_stats.add_row(
        "Air", str(_get_attr_or_key(character, "attack_air", 0)), f"{_get_attr_or_key(character, 'dmg_air', 0)}%"
    )
    attack_stats.add_row("General", "—", f"{_get_attr_or_key(character, 'dmg', 0)}%")

    # Resistance stats
    resistance_stats = Table(box=box.ROUNDED, title="Resistance Stats")
    resistance_stats.add_column("Element", style="blue")
    resistance_stats.add_column("Resistance %", justify="right", style="white")

    resistance_stats.add_row("Fire", f"{_get_attr_or_key(character, 'res_fire', 0)}%")
    resistance_stats.add_row("Earth", f"{_get_attr_or_key(character, 'res_earth', 0)}%")
    resistance_stats.add_row("Water", f"{_get_attr_or_key(character, 'res_water', 0)}%")
    resistance_stats.add_row("Air", f"{_get_attr_or_key(character, 'res_air', 0)}%")

    # Equipment info
    equipment_info = Table(box=box.ROUNDED, title="Equipment")
    equipment_info.add_column("Slot", style="cyan")
    equipment_info.add_column("Item", style="white")

    equipment_slots = [
        ("Weapon", "weapon_slot"),
        ("Shield", "shield_slot"),
        ("Helmet", "helmet_slot"),
        ("Body Armor", "body_armor_slot"),
        ("Leg Armor", "leg_armor_slot"),
        ("Boots", "boots_slot"),
        ("Ring 1", "ring1_slot"),
        ("Ring 2", "ring2_slot"),
        ("Amulet", "amulet_slot"),
        ("Artifact 1", "artifact1_slot"),
        ("Artifact 2", "artifact2_slot"),
        ("Artifact 3", "artifact3_slot"),
    ]

    for slot_name, slot_attr in equipment_slots:
        if hasattr(character, slot_attr):
            slot_item = getattr(character, slot_attr)
            if slot_item and hasattr(slot_item, "code"):
                equipment_info.add_row(slot_name, str(getattr(slot_item, "code", "N/A")))
            elif slot_item:
                equipment_info.add_row(slot_name, str(slot_item))
            else:
                equipment_info.add_row(slot_name, "None")

    # Task info
    task_info = Table(box=box.ROUNDED, title="Current Task")
    task_info.add_column("Property", style="cyan")
    task_info.add_column("Value", style="white")

    if hasattr(character, "task") and character.task:
        task = character.task
        task_info.add_row("Task Code", str(_get_attr_or_key(task, "code", "N/A")))
        task_info.add_row("Task Type", str(_get_attr_or_key(task, "type", "N/A")))
        task_info.add_row("Progress", f"{_get_attr_or_key(task, 'progress', 0)}/{_get_attr_or_key(task, 'total', 0)}")
    else:
        task_info.add_row("Status", "No active task")

    # Arrange tables in columns
    top_row = Columns([basic_info, gathering_skills], equal=True, expand=True)
    middle_row = Columns([crafting_skills, combat_stats], equal=True, expand=True)
    bottom_row = Columns([attack_stats, resistance_stats], equal=True, expand=True)
    equipment_row = Columns([equipment_info, task_info], equal=True, expand=True)

    # Create the main panel
    character_name = str(_get_attr_or_key(character, "name", "Unknown"))
    return Panel(
        f"{top_row}\n\n{middle_row}\n\n{bottom_row}\n\n{equipment_row}",
        title=f"[bold cyan]{character_name}'s Status[/bold cyan]",
        border_style="bright_blue",
    )

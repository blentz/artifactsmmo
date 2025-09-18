"""Character management commands."""

from datetime import datetime

import typer
from rich.console import Console

from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.utils.formatters import (
    format_character_table,
    format_error_message,
    format_success_message,
    format_table,
    format_time_duration,
)
from artifactsmmo_cli.utils.helpers import handle_api_error, handle_api_response
from artifactsmmo_cli.utils.validators import validate_character_name, validate_skin_code

app = typer.Typer(help="Character management commands")
console = Console()


@app.command("list")
def list_characters() -> None:
    """List all your characters."""
    try:
        api = ClientManager().api
        response = api.get_my_characters()

        if response and response.data:
            console.print(format_character_table(response.data))
        else:
            console.print(format_error_message("No characters found"))

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("create")
def create_character(
    name: str = typer.Argument(..., help="Character name"), skin: str = typer.Option("human1", help="Character skin")
) -> None:
    """Create a new character."""
    try:
        # Validate inputs
        name = validate_character_name(name)
        skin = validate_skin_code(skin)

        api = ClientManager().api

        # Import the schema for character creation
        from artifactsmmo_api_client.models.add_character_schema import AddCharacterSchema
        from artifactsmmo_api_client.models.character_skin import CharacterSkin

        character_data = AddCharacterSchema(name=name, skin=CharacterSkin(skin))
        response = api.create_character(character_data)

        if response:
            console.print(format_success_message(f"Character '{name}' created successfully"))
        else:
            console.print(format_error_message("Failed to create character"))
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("delete")
def delete_character(
    name: str = typer.Argument(..., help="Character name to delete"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Delete a character."""
    try:
        name = validate_character_name(name)

        # Confirmation prompt
        if not confirm:
            confirmed = typer.confirm(f"Are you sure you want to delete character '{name}'?")
            if not confirmed:
                console.print("Character deletion cancelled.")
                return

        api = ClientManager().api

        # Import the schema for character deletion
        from artifactsmmo_api_client.models.delete_character_schema import DeleteCharacterSchema

        delete_data = DeleteCharacterSchema(name=name)
        response = api.delete_character(body=delete_data)

        cli_response = handle_api_response(response, f"Character '{name}' deleted successfully")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Character deleted"))
        else:
            console.print(format_error_message(cli_response.error or "Failed to delete character"))
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("info")
def character_info(name: str = typer.Argument(..., help="Character name")) -> None:
    """Get detailed information about a character."""
    try:
        name = validate_character_name(name)

        api = ClientManager().api
        response = api.get_character(name=name)

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            # Format character info as a table
            char_data = [cli_response.data]  # Wrap single character in list for table formatter
            console.print(format_character_table(char_data))
        else:
            console.print(format_error_message(cli_response.error or f"Character '{name}' not found"))
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("inventory")
def character_inventory(name: str = typer.Argument(..., help="Character name")) -> None:
    """Show character's inventory."""
    try:
        name = validate_character_name(name)

        api = ClientManager().api
        response = api.get_character(name=name)

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            character = cli_response.data

            # Check if character has inventory
            if hasattr(character, "inventory") and character.inventory:
                headers = ["Slot", "Code", "Quantity"]
                rows = []
                for item in character.inventory:
                    rows.append(
                        [
                            str(getattr(item, "slot", "N/A")),
                            getattr(item, "code", "N/A"),
                            str(getattr(item, "quantity", 0)),
                        ]
                    )

                output = format_table(headers, rows, title=f"{name}'s Inventory")
                console.print(output)
            else:
                console.print(format_error_message(f"Character '{name}' has no inventory items"))
        else:
            console.print(format_error_message(cli_response.error or f"Character '{name}' not found"))
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("status")
def character_status(name: str = typer.Argument(..., help="Character name")) -> None:
    """Show detailed character status including skills and combat stats."""
    try:
        name = validate_character_name(name)

        api = ClientManager().api
        response = api.get_character(name=name)

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            character = cli_response.data

            # Print character name as header
            character_name = getattr(character, "name", "Unknown")
            console.print(f"\n[bold cyan]═══ {character_name}'s Status ═══[/bold cyan]\n")

            # Create and print individual tables

            # Basic character info
            basic_info = format_table(
                ["Property", "Value"],
                [
                    ["Name", str(getattr(character, "name", "N/A"))],
                    ["Level", str(getattr(character, "level", 0))],
                    ["Class", str(getattr(character, "class", "None"))],
                    ["XP", f"{getattr(character, 'xp', 0)}/{getattr(character, 'max_xp', 0)}"],
                    ["Gold", str(getattr(character, "gold", 0))],
                    ["HP", f"{getattr(character, 'hp', 0)}/{getattr(character, 'max_hp', 0)}"],
                    ["MP", f"{getattr(character, 'mp', 0)}/{getattr(character, 'max_mp', 0)}"],
                    ["Position", f"({getattr(character, 'x', 0)}, {getattr(character, 'y', 0)})"],
                    ["Cooldown", str(getattr(character, "cooldown", 0)) + " seconds"],
                    ["Cooldown Expiration", str(getattr(character, "cooldown_expiration", "N/A"))],
                ],
                title="Character Info",
            )

            # Gathering skills
            gathering_skills = format_table(
                ["Skill", "Level", "XP"],
                [
                    [
                        "Mining",
                        str(getattr(character, "mining_level", 0)),
                        f"{getattr(character, 'mining_xp', 0)}/{getattr(character, 'mining_max_xp', 0)}",
                    ],
                    [
                        "Woodcutting",
                        str(getattr(character, "woodcutting_level", 0)),
                        f"{getattr(character, 'woodcutting_xp', 0)}/{getattr(character, 'woodcutting_max_xp', 0)}",
                    ],
                    [
                        "Fishing",
                        str(getattr(character, "fishing_level", 0)),
                        f"{getattr(character, 'fishing_xp', 0)}/{getattr(character, 'fishing_max_xp', 0)}",
                    ],
                ],
                title="Gathering Skills",
            )

            # Crafting skills
            crafting_skills = format_table(
                ["Skill", "Level", "XP"],
                [
                    [
                        "Weaponcrafting",
                        str(getattr(character, "weaponcrafting_level", 0)),
                        f"{getattr(character, 'weaponcrafting_xp', 0)}/"
                        f"{getattr(character, 'weaponcrafting_max_xp', 0)}",
                    ],
                    [
                        "Gearcrafting",
                        str(getattr(character, "gearcrafting_level", 0)),
                        f"{getattr(character, 'gearcrafting_xp', 0)}/{getattr(character, 'gearcrafting_max_xp', 0)}",
                    ],
                    [
                        "Jewelrycrafting",
                        str(getattr(character, "jewelrycrafting_level", 0)),
                        f"{getattr(character, 'jewelrycrafting_xp', 0)}/"
                        f"{getattr(character, 'jewelrycrafting_max_xp', 0)}",
                    ],
                    [
                        "Cooking",
                        str(getattr(character, "cooking_level", 0)),
                        f"{getattr(character, 'cooking_xp', 0)}/{getattr(character, 'cooking_max_xp', 0)}",
                    ],
                    [
                        "Alchemy",
                        str(getattr(character, "alchemy_level", 0)),
                        f"{getattr(character, 'alchemy_xp', 0)}/{getattr(character, 'alchemy_max_xp', 0)}",
                    ],
                ],
                title="Crafting Skills",
            )

            # Combat stats
            combat_stats = format_table(
                ["Stat", "Value"],
                [
                    ["Haste", str(getattr(character, "haste", 0))],
                    ["Critical Strike", f"{getattr(character, 'critical_strike', 0)}%"],
                    ["Wisdom", str(getattr(character, "wisdom", 0))],
                    ["Prospecting", str(getattr(character, "prospecting", 0))],
                ],
                title="Combat Stats",
            )

            # Attack stats
            attack_stats = format_table(
                ["Element", "Attack", "Damage %"],
                [
                    ["Fire", str(getattr(character, "attack_fire", 0)), f"{getattr(character, 'dmg_fire', 0)}%"],
                    ["Earth", str(getattr(character, "attack_earth", 0)), f"{getattr(character, 'dmg_earth', 0)}%"],
                    ["Water", str(getattr(character, "attack_water", 0)), f"{getattr(character, 'dmg_water', 0)}%"],
                    ["Air", str(getattr(character, "attack_air", 0)), f"{getattr(character, 'dmg_air', 0)}%"],
                    ["General", "—", f"{getattr(character, 'dmg', 0)}%"],
                ],
                title="Attack Stats",
            )

            # Resistance stats
            resistance_stats = format_table(
                ["Element", "Resistance %"],
                [
                    ["Fire", f"{getattr(character, 'res_fire', 0)}%"],
                    ["Earth", f"{getattr(character, 'res_earth', 0)}%"],
                    ["Water", f"{getattr(character, 'res_water', 0)}%"],
                    ["Air", f"{getattr(character, 'res_air', 0)}%"],
                ],
                title="Resistance Stats",
            )

            # Equipment info
            equipment_rows = []
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
                        equipment_rows.append([slot_name, str(getattr(slot_item, "code", "N/A"))])
                    elif slot_item:
                        equipment_rows.append([slot_name, str(slot_item)])
                    else:
                        equipment_rows.append([slot_name, "None"])

            equipment_info = format_table(["Slot", "Item"], equipment_rows, title="Equipment")

            # Task info
            task_rows = []
            task_code = getattr(character, "task", None)
            if task_code:
                task_rows.extend(
                    [
                        ["Task Code", str(task_code)],
                        ["Task Type", str(getattr(character, "task_type", "N/A"))],
                        ["Progress", f"{getattr(character, 'task_progress', 0)}/{getattr(character, 'task_total', 0)}"],
                    ]
                )
            else:
                task_rows.append(["Status", "No active task"])

            task_info = format_table(["Property", "Value"], task_rows, title="Current Task")

            # Print all tables
            console.print(basic_info)
            console.print()
            console.print(gathering_skills)
            console.print()
            console.print(crafting_skills)
            console.print()
            console.print(combat_stats)
            console.print()
            console.print(attack_stats)
            console.print()
            console.print(resistance_stats)
            console.print()
            console.print(equipment_info)
            console.print()
            console.print(task_info)
        else:
            console.print(format_error_message(cli_response.error or f"Character '{name}' not found"))
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("cooldown")
def character_cooldown(name: str = typer.Argument(..., help="Character name")) -> None:
    """Check character's cooldown status."""
    try:
        name = validate_character_name(name)

        api = ClientManager().api
        response = api.get_character(name=name)

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            character = cli_response.data

            # Get cooldown information
            cooldown_seconds = getattr(character, "cooldown", 0)
            cooldown_expiration = getattr(character, "cooldown_expiration", None)

            if cooldown_seconds <= 0:
                console.print(f"✅ Character '{name}' is not on cooldown", style="bold green")
                return  # Exit with code 0
            else:
                # Format time remaining
                time_remaining = format_time_duration(cooldown_seconds)

                # Parse and format expiration time if available
                expiration_str = "Unknown"
                if cooldown_expiration:
                    try:
                        # Parse ISO format datetime
                        if isinstance(cooldown_expiration, str):
                            expiration_dt = datetime.fromisoformat(cooldown_expiration.replace("Z", "+00:00"))
                            expiration_str = expiration_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                        else:
                            expiration_str = str(cooldown_expiration)
                    except (ValueError, AttributeError):
                        expiration_str = str(cooldown_expiration)

                console.print(f"⏱️  Character '{name}' is on cooldown", style="bold red")
                console.print(f"   Time remaining: {time_remaining}", style="yellow")
                console.print(f"   Expires at: {expiration_str}", style="cyan")
                raise typer.Exit(1)
        else:
            console.print(format_error_message(cli_response.error or f"Character '{name}' not found"))
            raise typer.Exit(1)

    except typer.Exit:
        raise  # Re-raise typer.Exit to preserve exit codes
    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)

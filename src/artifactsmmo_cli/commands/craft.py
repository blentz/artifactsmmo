"""Crafting and recycling commands."""

import typer
from rich.console import Console

from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.utils.formatters import (
    format_cooldown_message,
    format_error_message,
    format_success_message,
    format_table,
)
from artifactsmmo_cli.utils.helpers import handle_api_error, handle_api_response
from artifactsmmo_cli.utils.validators import (
    validate_character_name,
    validate_item_code,
    validate_quantity,
)

app = typer.Typer(help="Crafting and recycling commands")
console = Console()


@app.command("craft")
def craft_item(
    character: str = typer.Argument(..., help="Character name"),
    item_code: str = typer.Argument(..., help="Item code to craft"),
    quantity: int = typer.Option(1, help="Quantity to craft"),
) -> None:
    """Craft an item."""
    try:
        character = validate_character_name(character)
        item_code = validate_item_code(item_code)
        quantity = validate_quantity(quantity)

        client = ClientManager().client

        # Import the crafting schema and API function
        from artifactsmmo_api_client.api.my_characters import action_crafting_my_name_action_crafting_post
        from artifactsmmo_api_client.models.crafting_schema import CraftingSchema

        craft_data = CraftingSchema(code=item_code, quantity=quantity)
        response = action_crafting_my_name_action_crafting_post.sync(client=client, name=character, body=craft_data)

        cli_response = handle_api_response(response, f"Crafted {quantity}x {item_code}")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Crafting completed"))
        elif cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or "Crafting failed"))
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("recycle")
def recycle_item(
    character: str = typer.Argument(..., help="Character name"),
    item_code: str = typer.Argument(..., help="Item code to recycle"),
    quantity: int = typer.Option(1, help="Quantity to recycle"),
) -> None:
    """Recycle an item."""
    try:
        character = validate_character_name(character)
        item_code = validate_item_code(item_code)
        quantity = validate_quantity(quantity)

        client = ClientManager().client

        # Import the recycling schema and API function
        from artifactsmmo_api_client.api.my_characters import action_recycling_my_name_action_recycling_post
        from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema

        recycle_data = SimpleItemSchema(code=item_code, quantity=quantity)
        response = action_recycling_my_name_action_recycling_post.sync(client=client, name=character, body=recycle_data)

        cli_response = handle_api_response(response, f"Recycled {quantity}x {item_code}")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Recycling completed"))
        elif cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or "Recycling failed"))
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("preview")
def preview_craft(
    character: str = typer.Argument(..., help="Character name"),
    item_code: str = typer.Argument(..., help="Item code to preview"),
) -> None:
    """Preview whether a character can craft an item."""
    try:
        character = validate_character_name(character)
        item_code = validate_item_code(item_code)

        client = ClientManager().client
        api = ClientManager().api

        # Import the API functions
        from artifactsmmo_api_client.api.items import get_all_items_items_get

        # Fetch item recipe information
        items_response = get_all_items_items_get.sync(
            client=client,
            name=item_code,
            page=1,
            size=1,
        )

        items_cli_response = handle_api_response(items_response)
        if not items_cli_response.success or not items_cli_response.data:
            console.print(format_error_message(f"Item '{item_code}' not found"))
            raise typer.Exit(1)

        # Find the specific item
        items = items_cli_response.data
        if not hasattr(items, "data") or not items.data:
            console.print(format_error_message(f"Item '{item_code}' not found"))
            raise typer.Exit(1)

        target_item = None
        for item in items.data:
            if getattr(item, "code", "") == item_code:
                target_item = item
                break

        if not target_item:
            console.print(format_error_message(f"Item '{item_code}' not found"))
            raise typer.Exit(1)

        # Check if item is craftable
        if not hasattr(target_item, "craft") or not target_item.craft:
            console.print(format_error_message(f"Item '{item_code}' is not craftable"))
            raise typer.Exit(1)

        craft_info = target_item.craft

        # Fetch character information
        character_response = api.get_character(name=character)
        char_cli_response = handle_api_response(character_response)
        if not char_cli_response.success or not char_cli_response.data:
            console.print(format_error_message(f"Character '{character}' not found"))
            raise typer.Exit(1)

        character_data = char_cli_response.data

        # Get character inventory
        inventory = {}
        if hasattr(character_data, "inventory") and character_data.inventory:
            for item in character_data.inventory:
                code = getattr(item, "code", "")
                quantity = getattr(item, "quantity", 0)
                if code:
                    inventory[code] = inventory.get(code, 0) + quantity

        # Get required materials
        required_materials = []
        if hasattr(craft_info, "items") and craft_info.items:
            for material in craft_info.items:
                material_code = getattr(material, "code", "")
                material_quantity = getattr(material, "quantity", 0)
                if material_code:
                    required_materials.append((material_code, material_quantity))

        # Check character skill level
        craft_skill = getattr(craft_info, "skill", "").lower()
        required_level = getattr(craft_info, "level", 0)

        # Map skill names to character attributes
        skill_mapping = {
            "weaponcrafting": "weaponcrafting_level",
            "gearcrafting": "gearcrafting_level",
            "jewelrycrafting": "jewelrycrafting_level",
            "cooking": "cooking_level",
            "alchemy": "alchemy_level",
        }

        character_skill_level = 0
        if craft_skill in skill_mapping:
            skill_attr = skill_mapping[craft_skill]
            character_skill_level = getattr(character_data, skill_attr, 0)

        # Create output
        from rich.table import Table
        from rich.text import Text

        # Header info
        header_text = Text()
        header_text.append("Craft Preview: ", style="bold cyan")
        header_text.append(f"{item_code}", style="bold yellow")

        # Skill requirement check
        skill_status = "✅" if character_skill_level >= required_level else "❌"
        skill_text = f"{skill_status} {craft_skill.title()}: {character_skill_level}/{required_level}"

        # Materials table
        materials_table = Table(title="Material Requirements", show_header=True, header_style="bold magenta")
        materials_table.add_column("Material", style="cyan")
        materials_table.add_column("Required", justify="right", style="yellow")
        materials_table.add_column("Available", justify="right", style="green")
        materials_table.add_column("Status", justify="center")

        all_materials_available = True

        if required_materials:
            for material_code, required_qty in required_materials:
                available_qty = inventory.get(material_code, 0)
                status = "✅" if available_qty >= required_qty else "❌"
                if available_qty < required_qty:
                    all_materials_available = False

                materials_table.add_row(material_code, str(required_qty), str(available_qty), status)
        else:
            materials_table.add_row("None", "0", "N/A", "✅")

        # Overall status
        can_craft = character_skill_level >= required_level and all_materials_available
        overall_status = "✅ Ready to craft!" if can_craft else "❌ Cannot craft yet"
        status_style = "bold green" if can_craft else "bold red"

        # Display results
        console.print()
        console.print(header_text)
        console.print()
        console.print(f"Skill Requirement: {skill_text}")
        console.print()
        console.print(materials_table)
        console.print()
        console.print(f"Status: {overall_status}", style=status_style)
        console.print()

        # Exit with appropriate code
        if not can_craft:
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("recipes")
def list_recipes(
    item_code: str = typer.Option(None, help="Filter by item code"),
    skill: str = typer.Option(None, help="Filter by crafting skill"),
    level: int = typer.Option(None, help="Filter by minimum level"),
    page: int = typer.Option(1, help="Page number"),
    size: int = typer.Option(50, help="Items per page"),
) -> None:
    """List available crafting recipes."""
    try:
        client = ClientManager().client

        # Import the API function
        from artifactsmmo_api_client.api.items import get_all_items_items_get
        from artifactsmmo_api_client.models.craft_skill import CraftSkill
        from artifactsmmo_api_client.types import UNSET

        # Convert skill string to CraftSkill enum if provided
        craft_skill_param = UNSET
        if skill:
            try:
                craft_skill_param = CraftSkill(skill)
            except ValueError:
                # If skill doesn't match enum, leave as UNSET
                craft_skill_param = UNSET

        # Use the items endpoint to get crafting information
        # The API doesn't seem to have a dedicated recipes endpoint,
        # so we'll get items and filter for craftable ones
        response = get_all_items_items_get.sync(
            client=client,
            craft_skill=craft_skill_param,
            min_level=level if level is not None else UNSET,
            name=item_code if item_code else UNSET,
            page=page,
            size=size,
        )

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            items = cli_response.data
            if hasattr(items, "data") and items.data:
                # Filter for items that have crafting information
                craftable_items = [item for item in items.data if hasattr(item, "craft") and item.craft]

                if craftable_items:
                    headers = ["Item", "Level", "Skill", "Materials"]
                    rows = []
                    for item in craftable_items:
                        craft_info = item.craft
                        materials = []
                        if hasattr(craft_info, "items") and craft_info.items:
                            for mat in craft_info.items:
                                materials.append(f"{getattr(mat, 'quantity', 1)}x {getattr(mat, 'code', 'Unknown')}")

                        rows.append(
                            [
                                getattr(item, "code", "Unknown"),
                                str(getattr(craft_info, "level", 0)),
                                getattr(craft_info, "skill", "Unknown"),
                                ", ".join(materials) if materials else "None",
                            ]
                        )

                    output = format_table(headers, rows, title="Crafting Recipes")
                    console.print(output)
                else:
                    console.print(format_error_message("No craftable items found"))
            else:
                console.print(format_error_message("No items found"))
        else:
            console.print(format_error_message(cli_response.error or "Could not retrieve recipes"))

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)

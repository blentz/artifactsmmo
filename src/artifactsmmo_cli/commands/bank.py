"""Bank operation commands."""

import time
from typing import Dict, List, Optional, Tuple

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.utils.formatters import (
    format_bank_table,
    format_cooldown_message,
    format_error_message,
    format_success_message,
)
from artifactsmmo_cli.utils.helpers import handle_api_error, handle_api_response
from artifactsmmo_cli.utils.validators import (
    validate_character_name,
    validate_gold_amount,
    validate_item_code,
    validate_quantity,
)

app = typer.Typer(help="Bank operation commands")
console = Console()

# Item type categories for filtering
ITEM_CATEGORIES = {
    "resource": ["ore", "wood", "fish", "mining", "woodcutting", "fishing"],
    "consumable": ["consumable", "food"],
    "equipment": ["weapon", "helmet", "body_armor", "leg_armor", "boots", "shield", "amulet", "ring"],
    "crafting": ["crafting_material", "ingredient"],
    "currency": ["currency"],
    "utility": ["utility", "tool"],
}

# Items to keep by default (essential items)
DEFAULT_KEEP_ITEMS = {
    "equipment": True,  # Keep all equipment
    "consumable": False,  # Don't keep consumables by default
    "currency": True,  # Keep currency
    "utility": True,  # Keep utility items
}


def get_character_inventory(character: str) -> List[Dict]:
    """Get character's inventory items."""
    try:
        api = ClientManager().api

        response = api.get_character(name=character)
        cli_response = handle_api_response(response)

        if cli_response.success and cli_response.data:
            character_data = cli_response.data
            if hasattr(character_data, "inventory") and character_data.inventory:
                return [
                    {
                        "code": getattr(item, "code", ""),
                        "quantity": getattr(item, "quantity", 0),
                        "slot": getattr(item, "slot", 0),
                    }
                    for item in character_data.inventory
                ]
        return []
    except Exception:
        return []


def get_item_info(item_code: str) -> Optional[Dict]:
    """Get item information including type and subtype."""
    try:
        client = ClientManager().client

        # Import the API function
        from artifactsmmo_api_client.api.items import get_item_items_code_get

        response = get_item_items_code_get.sync(client=client, code=item_code)
        cli_response = handle_api_response(response)

        if cli_response.success and cli_response.data:
            item = cli_response.data
            return {
                "code": getattr(item, "code", ""),
                "name": getattr(item, "name", ""),
                "type": getattr(item, "type_", ""),
                "subtype": getattr(item, "subtype", ""),
                "level": getattr(item, "level", 0),
                "tradeable": getattr(item, "tradeable", True),
            }
        return None
    except Exception:
        return None


def categorize_item(item_info: Dict) -> str:
    """Categorize an item based on its type and subtype."""
    # Handle both "type" and "type_" for compatibility
    item_type = (item_info.get("type_", "") or item_info.get("type", "")).lower()
    item_subtype = item_info.get("subtype", "").lower()

    for category, types in ITEM_CATEGORIES.items():
        if item_type in types or item_subtype in types:
            return category

    return "other"


def filter_items_by_type(inventory: List[Dict], item_type: str) -> List[Dict]:
    """Filter inventory items by type category."""
    filtered_items = []

    for item in inventory:
        item_info = get_item_info(item["code"])
        if item_info:
            category = categorize_item(item_info)
            if category == item_type.lower():
                item["item_info"] = item_info
                filtered_items.append(item)

    return filtered_items


def should_keep_item(item_info: Dict, keep_equipment: bool = True, keep_consumables: bool = False) -> bool:
    """Determine if an item should be kept based on its category."""
    category = categorize_item(item_info)

    if category == "equipment" and keep_equipment:
        return True
    if category == "consumable" and keep_consumables:
        return True
    if category in ["currency", "utility"]:
        return True

    return False


def execute_single_deposit(character: str, item_code: str, quantity: int) -> Tuple[bool, Optional[str], Optional[int]]:
    """Execute a single deposit operation. Returns (success, error_message, cooldown_remaining)."""
    try:
        client = ClientManager().client

        # Import the simple item schema and API function
        from artifactsmmo_api_client.api.my_characters import (
            action_deposit_bank_item_my_name_action_bank_deposit_item_post,
        )
        from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema

        deposit_data = SimpleItemSchema(code=item_code, quantity=quantity)
        response = action_deposit_bank_item_my_name_action_bank_deposit_item_post.sync(
            client=client, name=character, body=deposit_data
        )

        cli_response = handle_api_response(response, f"Deposited {quantity}x {item_code}")

        if cli_response.success:
            return True, None, None
        elif cli_response.cooldown_remaining:
            return False, None, cli_response.cooldown_remaining
        else:
            return False, cli_response.error or "Deposit failed", None

    except Exception as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            return False, None, cli_response.cooldown_remaining
        else:
            return False, cli_response.error or str(e), None


def execute_single_withdraw(character: str, item_code: str, quantity: int) -> Tuple[bool, Optional[str], Optional[int]]:
    """Execute a single withdraw operation. Returns (success, error_message, cooldown_remaining)."""
    try:
        client = ClientManager().client

        # Import the simple item schema and API function
        from artifactsmmo_api_client.api.my_characters import (
            action_withdraw_bank_item_my_name_action_bank_withdraw_item_post,
        )
        from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema

        withdraw_data = SimpleItemSchema(code=item_code, quantity=quantity)
        response = action_withdraw_bank_item_my_name_action_bank_withdraw_item_post.sync(
            client=client, name=character, body=withdraw_data
        )

        cli_response = handle_api_response(response, f"Withdrew {quantity}x {item_code}")

        if cli_response.success:
            return True, None, None
        elif cli_response.cooldown_remaining:
            return False, None, cli_response.cooldown_remaining
        else:
            return False, cli_response.error or "Withdrawal failed", None

    except Exception as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            return False, None, cli_response.cooldown_remaining
        else:
            return False, cli_response.error or str(e), None


@app.command("list")
def list_bank_items() -> None:
    """List all items in your bank."""
    try:
        client = ClientManager().client

        # Import the API function
        from artifactsmmo_api_client.api.my_account import get_bank_items_my_bank_items_get

        response = get_bank_items_my_bank_items_get.sync(client=client)

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            console.print(format_bank_table(cli_response.data))
        else:
            console.print(format_error_message(cli_response.error or "No bank items found"))

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("details")
def bank_details() -> None:
    """Show bank details including gold and expansion info."""
    try:
        client = ClientManager().client

        # Import the API function
        from artifactsmmo_api_client.api.my_account import get_bank_details_my_bank_get

        response = get_bank_details_my_bank_get.sync(client=client)

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            bank_data = cli_response.data
            console.print(f"Bank Gold: {bank_data.get('gold', 0)}")
            console.print(f"Bank Slots: {bank_data.get('slots', 0)}")
            console.print(f"Expansion Cost: {bank_data.get('next_expansion_cost', 'N/A')}")
        else:
            console.print(format_error_message(cli_response.error or "Could not get bank details"))
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("deposit-gold")
def deposit_gold(
    character: str = typer.Argument(..., help="Character name"),
    amount: int = typer.Argument(..., help="Amount of gold to deposit"),
) -> None:
    """Deposit gold to bank."""
    try:
        character = validate_character_name(character)
        amount = validate_gold_amount(amount)

        client = ClientManager().client

        # Import the deposit gold schema and API function
        from artifactsmmo_api_client.api.my_characters import (
            action_deposit_bank_gold_my_name_action_bank_deposit_gold_post,
        )
        from artifactsmmo_api_client.models.deposit_withdraw_gold_schema import DepositWithdrawGoldSchema

        deposit_data = DepositWithdrawGoldSchema(quantity=amount)
        response = action_deposit_bank_gold_my_name_action_bank_deposit_gold_post.sync(
            client=client, name=character, body=deposit_data
        )

        cli_response = handle_api_response(response, f"Deposited {amount} gold")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Gold deposited"))
        elif cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or "Deposit failed"))
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("withdraw-gold")
def withdraw_gold(
    character: str = typer.Argument(..., help="Character name"),
    amount: int = typer.Argument(..., help="Amount of gold to withdraw"),
) -> None:
    """Withdraw gold from bank."""
    try:
        character = validate_character_name(character)
        amount = validate_gold_amount(amount)

        client = ClientManager().client

        # Import the withdraw gold schema and API function
        from artifactsmmo_api_client.api.my_characters import (
            action_withdraw_bank_gold_my_name_action_bank_withdraw_gold_post,
        )
        from artifactsmmo_api_client.models.deposit_withdraw_gold_schema import DepositWithdrawGoldSchema

        withdraw_data = DepositWithdrawGoldSchema(quantity=amount)
        response = action_withdraw_bank_gold_my_name_action_bank_withdraw_gold_post.sync(
            client=client, name=character, body=withdraw_data
        )

        cli_response = handle_api_response(response, f"Withdrew {amount} gold")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Gold withdrawn"))
        elif cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or "Withdrawal failed"))
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("deposit-item")
def deposit_item(
    character: str = typer.Argument(..., help="Character name"),
    item_code: str = typer.Argument(..., help="Item code to deposit"),
    quantity: int = typer.Argument(..., help="Quantity to deposit"),
) -> None:
    """Deposit items to bank."""
    try:
        character = validate_character_name(character)
        item_code = validate_item_code(item_code)
        quantity = validate_quantity(quantity)

        client = ClientManager().client

        # Import the simple item schema and API function
        from artifactsmmo_api_client.api.my_characters import (
            action_deposit_bank_item_my_name_action_bank_deposit_item_post,
        )
        from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema

        deposit_data = SimpleItemSchema(code=item_code, quantity=quantity)
        response = action_deposit_bank_item_my_name_action_bank_deposit_item_post.sync(
            client=client, name=character, body=deposit_data
        )

        cli_response = handle_api_response(response, f"Deposited {quantity}x {item_code}")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Item deposited"))
        elif cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or "Deposit failed"))
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("withdraw-item")
def withdraw_item(
    character: str = typer.Argument(..., help="Character name"),
    item_code: str = typer.Argument(..., help="Item code to withdraw"),
    quantity: int = typer.Argument(..., help="Quantity to withdraw"),
) -> None:
    """Withdraw items from bank."""
    try:
        character = validate_character_name(character)
        item_code = validate_item_code(item_code)
        quantity = validate_quantity(quantity)

        client = ClientManager().client

        # Import the simple item schema and API function
        from artifactsmmo_api_client.api.my_characters import (
            action_withdraw_bank_item_my_name_action_bank_withdraw_item_post,
        )
        from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema

        withdraw_data = SimpleItemSchema(code=item_code, quantity=quantity)
        response = action_withdraw_bank_item_my_name_action_bank_withdraw_item_post.sync(
            client=client, name=character, body=withdraw_data
        )

        cli_response = handle_api_response(response, f"Withdrew {quantity}x {item_code}")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Item withdrawn"))
        elif cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or "Withdrawal failed"))
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("expand")
def buy_expansion(character: str = typer.Argument(..., help="Character name")) -> None:
    """Buy bank expansion."""
    try:
        character = validate_character_name(character)

        client = ClientManager().client

        # Import the API function
        from artifactsmmo_api_client.api.my_characters import (
            action_buy_bank_expansion_my_name_action_bank_buy_expansion_post,
        )

        response = action_buy_bank_expansion_my_name_action_bank_buy_expansion_post.sync(client=client, name=character)

        cli_response = handle_api_response(response, "Bank expansion purchased")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Bank expanded"))
        elif cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or "Expansion failed"))
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("deposit-all")
def deposit_all_items(
    character: str = typer.Argument(..., help="Character name"),
    item_type: Optional[str] = typer.Option(
        None, "--type", help="Filter by item type (resource, consumable, equipment, crafting)"
    ),
    keep_equipment: bool = typer.Option(True, "--keep-equipment/--no-keep-equipment", help="Keep equipment items"),
    keep_consumables: bool = typer.Option(
        False, "--keep-consumables/--no-keep-consumables", help="Keep consumable items"
    ),
    continue_on_error: bool = typer.Option(False, "--continue-on-error", help="Continue on individual item errors"),
) -> None:
    """Deposit all items from character's inventory to bank."""
    try:
        character = validate_character_name(character)

        # Get character inventory
        inventory = get_character_inventory(character)
        if not inventory:
            console.print(format_error_message(f"Character '{character}' has no inventory items"))
            return

        # Filter items if type specified
        if item_type:
            inventory = filter_items_by_type(inventory, item_type)
            if not inventory:
                console.print(format_error_message(f"No items of type '{item_type}' found in inventory"))
                return

        # Filter out items to keep
        items_to_deposit = []
        for item in inventory:
            if "item_info" not in item:
                item_info = get_item_info(item["code"])
                if not item_info:
                    continue
                item["item_info"] = item_info

            if not should_keep_item(item["item_info"], keep_equipment, keep_consumables):
                items_to_deposit.append(item)

        if not items_to_deposit:
            console.print(format_success_message("No items to deposit (all items are marked to keep)"))
            return

        # Execute bulk deposit with progress tracking
        successful_deposits = []
        failed_deposits = []
        total_items = len(items_to_deposit)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Depositing {total_items} items...", total=total_items)

            for i, item in enumerate(items_to_deposit):
                item_code = item["code"]
                quantity = item["quantity"]
                item_name = item["item_info"].get("name", item_code)

                progress.update(task, description=f"Depositing {item_name} ({quantity}x)")

                success, error, cooldown = execute_single_deposit(character, item_code, quantity)

                if success:
                    successful_deposits.append((item_code, item_name, quantity))
                elif cooldown:
                    # Handle cooldown
                    progress.update(task, description=f"Waiting for cooldown ({cooldown}s)...")
                    time.sleep(cooldown)
                    # Retry the operation
                    success, error, _ = execute_single_deposit(character, item_code, quantity)
                    if success:
                        successful_deposits.append((item_code, item_name, quantity))
                    else:
                        failed_deposits.append((item_code, item_name, quantity, error or "Unknown error"))
                        if not continue_on_error:
                            break
                else:
                    failed_deposits.append((item_code, item_name, quantity, error or "Unknown error"))
                    if not continue_on_error:
                        break

                progress.advance(task)

        # Display summary
        _display_operation_summary("Deposit", successful_deposits, failed_deposits)

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("withdraw-all")
def withdraw_all_items(
    character: str = typer.Argument(..., help="Character name"),
    item_code: str = typer.Argument(..., help="Item code to withdraw all of"),
    continue_on_error: bool = typer.Option(False, "--continue-on-error", help="Continue on errors"),
) -> None:
    """Withdraw all of a specific item from bank to character's inventory."""
    try:
        character = validate_character_name(character)
        item_code = validate_item_code(item_code)

        # Get bank items to find how many we have
        client = ClientManager().client
        from artifactsmmo_api_client.api.my_account import get_bank_items_my_bank_items_get

        response = get_bank_items_my_bank_items_get.sync(client=client)
        cli_response = handle_api_response(response)

        if not cli_response.success or cli_response.data is None:
            console.print(format_error_message("Could not retrieve bank items"))
            raise typer.Exit(1)

        # Find the item in bank
        bank_items = cli_response.data
        target_item = None
        for item in bank_items:
            if getattr(item, "code", "") == item_code:
                target_item = item
                break

        if not target_item:
            console.print(format_error_message(f"Item '{item_code}' not found in bank"))
            return

        total_quantity = getattr(target_item, "quantity", 0)
        if total_quantity <= 0:
            console.print(format_error_message(f"No '{item_code}' items in bank"))
            return

        # Get item info for display
        item_info = get_item_info(item_code)
        item_name = item_info.get("name", item_code) if item_info else item_code

        console.print(f"Withdrawing {total_quantity}x {item_name} from bank...")

        # Execute withdrawal
        success, error, cooldown = execute_single_withdraw(character, item_code, total_quantity)

        if success:
            console.print(format_success_message(f"Successfully withdrew {total_quantity}x {item_name}"))
        elif cooldown:
            console.print(format_cooldown_message(cooldown))
        else:
            console.print(format_error_message(error or "Withdrawal failed"))
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("exchange")
def smart_exchange(
    character: str = typer.Argument(..., help="Character name"),
    deposit_resources: bool = typer.Option(
        True, "--deposit-resources/--no-deposit-resources", help="Deposit resource items"
    ),
    keep_consumables: bool = typer.Option(
        True, "--keep-consumables/--no-keep-consumables", help="Keep consumable items"
    ),
    continue_on_error: bool = typer.Option(False, "--continue-on-error", help="Continue on individual item errors"),
) -> None:
    """Smart exchange: deposit resources, keep crafting materials and equipment."""
    try:
        character = validate_character_name(character)

        # Get character inventory
        inventory = get_character_inventory(character)
        if not inventory:
            console.print(format_error_message(f"Character '{character}' has no inventory items"))
            return

        # Categorize items for smart exchange
        items_to_deposit = []
        items_to_keep = []

        for item in inventory:
            item_info = get_item_info(item["code"])
            if not item_info:
                continue

            item["item_info"] = item_info
            category = categorize_item(item_info)

            # Smart exchange logic
            if category == "equipment":
                items_to_keep.append(item)  # Always keep equipment
            elif category == "consumable" and keep_consumables:
                items_to_keep.append(item)
            elif category in ["crafting", "utility", "currency"]:
                items_to_keep.append(item)  # Keep crafting materials and utilities
            elif category == "resource" and deposit_resources:
                items_to_deposit.append(item)
            elif category == "resource" and not deposit_resources:
                items_to_keep.append(item)  # Keep resources if not depositing them
            else:
                items_to_deposit.append(item)

        if not items_to_deposit:
            console.print(format_success_message("No items to deposit in smart exchange"))
            return

        # Display exchange plan
        console.print("\n[bold]Smart Exchange Plan:[/bold]")
        console.print(f"Items to deposit: {len(items_to_deposit)}")
        console.print(f"Items to keep: {len(items_to_keep)}")

        # Execute deposits
        successful_deposits = []
        failed_deposits = []
        total_items = len(items_to_deposit)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Smart exchange: depositing {total_items} items...", total=total_items)

            for item in items_to_deposit:
                item_code = item["code"]
                quantity = item["quantity"]
                item_name = item["item_info"].get("name", item_code)

                progress.update(task, description=f"Depositing {item_name} ({quantity}x)")

                success, error, cooldown = execute_single_deposit(character, item_code, quantity)

                if success:
                    successful_deposits.append((item_code, item_name, quantity))
                elif cooldown:
                    progress.update(task, description=f"Waiting for cooldown ({cooldown}s)...")
                    time.sleep(cooldown)
                    success, error, _ = execute_single_deposit(character, item_code, quantity)
                    if success:
                        successful_deposits.append((item_code, item_name, quantity))
                    else:
                        failed_deposits.append((item_code, item_name, quantity, error or "Unknown error"))
                        if not continue_on_error:
                            break
                else:
                    failed_deposits.append((item_code, item_name, quantity, error or "Unknown error"))
                    if not continue_on_error:
                        break

                progress.advance(task)

        # Display summary
        _display_operation_summary("Smart Exchange", successful_deposits, failed_deposits)

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


def _display_operation_summary(
    operation_name: str, successful_operations: List[Tuple], failed_operations: List[Tuple]
) -> None:
    """Display a summary of bulk operations."""
    console.print(f"\n[bold]{operation_name} Summary:[/bold]")

    if successful_operations:
        console.print(f"[green]✓ Successfully processed {len(successful_operations)} items:[/green]")

        # Create summary table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Item Code", style="cyan")
        table.add_column("Item Name", style="white")
        table.add_column("Quantity", justify="right", style="green")

        for item_code, item_name, quantity in successful_operations:
            table.add_row(item_code, item_name, str(quantity))

        console.print(table)

    if failed_operations:
        console.print(f"\n[red]✗ Failed to process {len(failed_operations)} items:[/red]")

        # Create error table
        error_table = Table(show_header=True, header_style="bold red")
        error_table.add_column("Item Code", style="cyan")
        error_table.add_column("Item Name", style="white")
        error_table.add_column("Quantity", justify="right", style="yellow")
        error_table.add_column("Error", style="red")

        for item_code, item_name, quantity, error in failed_operations:
            error_table.add_row(item_code, item_name, str(quantity), error)

        console.print(error_table)

    # Overall summary
    total_attempted = len(successful_operations) + len(failed_operations)
    success_rate = (len(successful_operations) / total_attempted * 100) if total_attempted > 0 else 0

    console.print(
        f"\n[bold]Overall: {len(successful_operations)}/{total_attempted} operations successful ({success_rate:.1f}%)[/bold]"
    )

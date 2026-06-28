"""Character action commands."""

import math
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import typer
from artifactsmmo_api_client.errors import UnexpectedStatus
from artifactsmmo_api_client.models.destination_schema import DestinationSchema
from artifactsmmo_api_client.models.equip_schema import EquipSchema
from artifactsmmo_api_client.models.item_slot import ItemSlot
from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema
from artifactsmmo_api_client.models.unequip_schema import UnequipSchema
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.models.responses import CLIResponse
from artifactsmmo_cli.utils.formatters import (
    format_combat_result,
    format_cooldown_message,
    format_error_message,
    format_gathering_result,
    format_success_message,
    format_time_duration,
)
from artifactsmmo_cli.utils.helpers import handle_api_error, handle_api_response
from artifactsmmo_cli.utils.pathfinding import (
    calculate_path,
    get_character_position,
    parse_destination,
    resolve_named_location,
)
from artifactsmmo_cli.utils.validators import (
    validate_character_name,
    validate_coordinates,
    validate_item_code,
    validate_item_slot,
    validate_quantity,
)

app = typer.Typer(help="Character action commands")
console = Console()


@dataclass
class BatchResults:
    """Track accumulated results from batch operations."""

    total_attempts: int = 0
    successful_actions: int = 0
    failed_actions: int = 0
    total_xp: int = 0
    total_gold: int = 0
    items_collected: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    start_time: float = field(default_factory=time.time)
    errors: list[str] = field(default_factory=list)

    def add_success(self, response_data: dict[str, Any] | None = None) -> None:
        """Add a successful action result."""
        self.successful_actions += 1

        if not response_data:
            return

        # Extract XP from various possible locations
        if "xp" in response_data:
            self.total_xp += response_data["xp"]
        elif "details" in response_data and isinstance(response_data["details"], dict):
            self.total_xp += response_data["details"].get("xp", 0)
        elif "fight" in response_data and isinstance(response_data["fight"], dict):
            self.total_xp += response_data["fight"].get("xp", 0)

        # Extract gold
        if "gold" in response_data:
            self.total_gold += response_data["gold"]
        elif "details" in response_data and isinstance(response_data["details"], dict):
            self.total_gold += response_data["details"].get("gold", 0)
        elif "fight" in response_data and isinstance(response_data["fight"], dict):
            self.total_gold += response_data["fight"].get("gold", 0)

        # Extract items from gathering
        if "details" in response_data and isinstance(response_data["details"], dict):
            items = response_data["details"].get("items", [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and "code" in item and "quantity" in item:
                        self.items_collected[item["code"]] += item["quantity"]

        # Extract items from combat drops
        if "fight" in response_data and isinstance(response_data["fight"], dict):
            drops = response_data["fight"].get("drops", [])
            if isinstance(drops, list):
                for drop in drops:
                    if isinstance(drop, dict) and "code" in drop and "quantity" in drop:
                        self.items_collected[drop["code"]] += drop["quantity"]

    def add_failure(self, error: str) -> None:
        """Add a failed action result."""
        self.failed_actions += 1
        self.errors.append(error)

    def get_elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time

    def format_summary(self) -> Table:
        """Format results as a summary table."""
        table = Table(title="Batch Operation Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")

        elapsed = self.get_elapsed_time()
        avg_time = elapsed / self.total_attempts if self.total_attempts > 0 else 0

        table.add_row("Total Attempts", str(self.total_attempts))
        table.add_row("Successful Actions", str(self.successful_actions))
        table.add_row("Failed Actions", str(self.failed_actions))
        table.add_row(
            "Success Rate",
            f"{(self.successful_actions / self.total_attempts * 100):.1f}%" if self.total_attempts > 0 else "0%",
        )
        table.add_row("Total XP Gained", str(self.total_xp))
        table.add_row("Total Gold Gained", str(self.total_gold))
        table.add_row("Total Time", format_time_duration(int(elapsed)))
        table.add_row("Average Time/Action", f"{avg_time:.1f}s")

        if self.items_collected:
            items_str = ", ".join([f"{qty}x {code}" for code, qty in self.items_collected.items()])
            table.add_row("Items Collected", items_str)

        return table


def execute_gather_action(character: str) -> CLIResponse[Any]:
    """Execute a gather action and return the result."""
    try:
        character = validate_character_name(character)
        api = ClientManager().api
        response = api.action_gathering(name=character)
        return handle_api_response(response, f"{character} gathered resources")
    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        return handle_api_error(e)


def execute_fight_action(character: str) -> CLIResponse[Any]:
    """Execute a fight action and return the result."""
    try:
        character = validate_character_name(character)
        api = ClientManager().api
        response = api.action_fight(name=character)
        return handle_api_response(response, f"{character} engaged in combat")
    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        return handle_api_error(e)


def execute_rest_action(character: str) -> CLIResponse[Any]:
    """Execute a rest action and return the result."""
    try:
        character = validate_character_name(character)
        api = ClientManager().api
        response = api.action_rest(name=character)
        return handle_api_response(response, f"{character} is resting")
    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        return handle_api_error(e)


# Action mapping for batch operations
ACTION_EXECUTORS: dict[str, Callable[[str], CLIResponse[Any]]] = {
    "gather": execute_gather_action,
    "fight": execute_fight_action,
    "rest": execute_rest_action,
}


@app.command("move")
def move_character(
    character: str = typer.Argument(..., help="Character name"),
    x: int = typer.Argument(..., help="X coordinate"),
    y: int = typer.Argument(..., help="Y coordinate"),
) -> None:
    """Move character to coordinates."""
    try:
        character = validate_character_name(character)
        x, y = validate_coordinates(x, y)

        api = ClientManager().api

        destination = DestinationSchema(x=x, y=y)
        response = api.action_move(name=character, body=destination)

        cli_response = handle_api_response(response, f"Moved {character} to ({x}, {y})")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Move completed"))
        else:
            console.print(format_error_message(cli_response.error or "Move failed"))
            raise typer.Exit(1)

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("fight")
def fight_monster(character: str = typer.Argument(..., help="Character name")) -> None:
    """Fight a monster at current location."""
    try:
        character = validate_character_name(character)

        api = ClientManager().api
        response = api.action_fight(name=character)

        cli_response = handle_api_response(response, f"{character} engaged in combat")
        if cli_response.success and cli_response.data:
            # Try to extract and display detailed combat results
            fight_data = cli_response.data
            if isinstance(fight_data, dict) and "fight" in fight_data:
                console.print(format_combat_result(fight_data["fight"]))
            else:
                console.print(format_success_message(cli_response.message or "Combat completed"))
        else:
            console.print(format_error_message(cli_response.error or "Combat failed"))
            raise typer.Exit(1)

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("gather")
def gather_resource(character: str = typer.Argument(..., help="Character name")) -> None:
    """Gather resources at current location."""
    try:
        character = validate_character_name(character)

        api = ClientManager().api
        response = api.action_gathering(name=character)

        cli_response = handle_api_response(response, f"{character} gathered resources")
        if cli_response.success and cli_response.data:
            # Try to extract and display detailed gathering results
            gather_data = cli_response.data
            if isinstance(gather_data, dict) and "details" in gather_data:
                console.print(format_gathering_result(gather_data["details"]))
            else:
                console.print(format_success_message(cli_response.message or "Gathering completed"))
        else:
            console.print(format_error_message(cli_response.error or "Gathering failed"))
            raise typer.Exit(1)

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("rest")
def rest_character(character: str = typer.Argument(..., help="Character name")) -> None:
    """Rest to recover HP and MP."""
    try:
        character = validate_character_name(character)

        api = ClientManager().api
        response = api.action_rest(name=character)

        cli_response = handle_api_response(response, f"{character} is resting")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Rest completed"))
        else:
            console.print(format_error_message(cli_response.error or "Rest failed"))
            raise typer.Exit(1)

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("equip")
def equip_item(
    character: str = typer.Argument(..., help="Character name"),
    item_code: str = typer.Argument(..., help="Item code to equip"),
    slot: str = typer.Argument(..., help="Equipment slot"),
    quantity: int = typer.Option(1, help="Quantity to equip"),
) -> None:
    """Equip an item."""
    try:
        character = validate_character_name(character)
        item_code = validate_item_code(item_code)
        slot = validate_item_slot(slot)
        quantity = validate_quantity(quantity)

        api = ClientManager().api

        equip_data = EquipSchema(code=item_code, slot=ItemSlot(slot), quantity=quantity)
        response = api.action_equip_item(name=character, body=[equip_data])

        cli_response = handle_api_response(response, f"Equipped {item_code} on {character}")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Item equipped"))
        else:
            console.print(format_error_message(cli_response.error or "Equip failed"))
            raise typer.Exit(1)

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("unequip")
def unequip_item(
    character: str = typer.Argument(..., help="Character name"),
    slot: str = typer.Argument(..., help="Equipment slot to unequip"),
    quantity: int = typer.Option(1, help="Quantity to unequip"),
) -> None:
    """Unequip an item."""
    try:
        character = validate_character_name(character)
        slot = validate_item_slot(slot)
        quantity = validate_quantity(quantity)

        api = ClientManager().api

        unequip_data = UnequipSchema(slot=ItemSlot(slot), quantity=quantity)
        response = api.action_unequip_item(name=character, body=[unequip_data])

        cli_response = handle_api_response(response, f"Unequipped {slot} from {character}")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Item unequipped"))
        else:
            console.print(format_error_message(cli_response.error or "Unequip failed"))
            raise typer.Exit(1)

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("use")
def use_item(
    character: str = typer.Argument(..., help="Character name"),
    item_code: str = typer.Argument(..., help="Item code to use"),
    quantity: int = typer.Option(1, help="Quantity to use"),
) -> None:
    """Use an item."""
    try:
        character = validate_character_name(character)
        item_code = validate_item_code(item_code)
        quantity = validate_quantity(quantity)

        api = ClientManager().api

        use_data = SimpleItemSchema(code=item_code, quantity=quantity)
        response = api.action_use_item(name=character, body=use_data)

        cli_response = handle_api_response(response, f"Used {quantity}x {item_code}")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Item used"))
        else:
            console.print(format_error_message(cli_response.error or "Use item failed"))
            raise typer.Exit(1)

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("goto")
def goto_location(
    character: str = typer.Argument(..., help="Character name"),
    destination: str = typer.Argument(
        ..., help="Destination (X Y coordinates or named location like 'bank', 'task master', 'copper')"
    ),
    y: int = typer.Argument(None, help="Y coordinate (if X coordinate provided as destination)"),
    wait_cooldown: bool = typer.Option(
        True, "--wait-cooldown/--no-wait-cooldown", "-w", help="Wait for cooldowns between moves"
    ),
    show_path: bool = typer.Option(False, "--show-path", "-p", help="Show path before moving"),
) -> None:
    """Navigate character to a destination automatically.

    Examples:
        action goto mychar 5 10          # Go to coordinates (5, 10)
        action goto mychar "5 10"        # Go to coordinates (5, 10) - quoted
        action goto mychar bank          # Go to nearest bank
        action goto mychar "task master" # Go to nearest task master
        action goto mychar copper        # Go to nearest copper resource
    """
    try:
        character = validate_character_name(character)

        # Get character's current position
        try:
            start_x, start_y = get_character_position(character)
        except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
            console.print(format_error_message(f"Could not get character position: {e!s}"))
            raise typer.Exit(1)

        # Parse destination - handle both "X Y" format and separate X Y arguments
        if y is not None:
            # Separate X Y arguments provided
            try:
                end_x = int(destination)
                end_y = y
                end_x, end_y = validate_coordinates(end_x, end_y)
            except ValueError:
                console.print(format_error_message(f"Invalid coordinates: '{destination}' is not a valid X coordinate"))
                raise typer.Exit(1)
        else:
            # Single destination argument - parse as coordinates or named location
            parsed_dest = parse_destination(destination)

            if isinstance(parsed_dest, tuple):
                # Coordinates provided as "X Y"
                end_x, end_y = parsed_dest
                end_x, end_y = validate_coordinates(end_x, end_y)
            else:
                # Named location
                try:
                    end_x, end_y = resolve_named_location(parsed_dest, start_x, start_y)
                except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
                    console.print(format_error_message(f"Could not find location '{parsed_dest}': {e!s}"))
                    raise typer.Exit(1)

        # Show current position and destination
        console.print(f"[bold cyan]Navigation for {character}[/bold cyan]")
        console.print(f"[dim]From: ({start_x}, {start_y}) → To: ({end_x}, {end_y})[/dim]")
        console.print()

        # If no movement needed
        if start_x == end_x and start_y == end_y:
            console.print(format_success_message(f"{character} is already at the destination"))
            return

        # Ask for confirmation if requested
        if show_path and not typer.confirm(f"Move to ({end_x}, {end_y})?"):
            console.print("Navigation cancelled.")
            return

        # The server runs A* pathfinding and moves the character all the way to the
        # destination in a single action (cooldown scales with the path it takes),
        # so the client issues one move rather than walking tile-by-tile.
        destination_data = DestinationSchema(x=end_x, y=end_y)

        def attempt_move() -> CLIResponse[Any]:
            response = ClientManager().api.action_move(name=character, body=destination_data)
            return handle_api_response(response, f"Moved {character} to ({end_x}, {end_y})")

        try:
            cli_response = attempt_move()
        except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
            cli_response = handle_api_error(e)

        # On cooldown: wait and retry once if allowed, otherwise stop.
        if not cli_response.success and cli_response.cooldown_remaining:
            cooldown_seconds = cli_response.cooldown_remaining
            console.print(format_cooldown_message(cooldown_seconds))
            if not wait_cooldown:
                console.print(
                    format_error_message(f"Move blocked by cooldown ({format_time_duration(cooldown_seconds)})")
                )
                return
            console.print(f"[blue]⏱ Waiting {format_time_duration(cooldown_seconds)} for cooldown...[/blue]")
            for remaining in range(math.ceil(cooldown_seconds), 0, -1):
                console.print(f"[dim]Waiting for cooldown: {remaining}s remaining[/dim]")
                time.sleep(1)
            try:
                cli_response = attempt_move()
            except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
                cli_response = handle_api_error(e)

        if cli_response.success:
            console.print(format_success_message(f"🎯 {character} reached destination ({end_x}, {end_y})"))
        else:
            console.print(format_error_message(cli_response.error or "Move failed"))

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        console.print(format_error_message(f"Navigation failed: {e!s}"))
        raise typer.Exit(1)


@app.command("path")
def show_path_command(
    character: str = typer.Argument(..., help="Character name"),
    destination: str = typer.Argument(
        ..., help="Destination (X Y coordinates or named location like 'bank', 'task master', 'copper')"
    ),
    y: int = typer.Argument(None, help="Y coordinate (if X coordinate provided as destination)"),
) -> None:
    """Show the path to a destination without moving.

    Examples:
        action path mychar 5 10          # Show path to coordinates (5, 10)
        action path mychar "5 10"        # Show path to coordinates (5, 10) - quoted
        action path mychar bank          # Show path to nearest bank
        action path mychar "task master" # Show path to nearest task master
        action path mychar copper        # Show path to nearest copper resource
    """
    try:
        character = validate_character_name(character)

        # Get character's current position
        try:
            start_x, start_y = get_character_position(character)
        except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
            console.print(format_error_message(f"Could not get character position: {e!s}"))
            raise typer.Exit(1)

        # Parse destination - handle both "X Y" format and separate X Y arguments
        if y is not None:
            # Separate X Y arguments provided
            try:
                end_x = int(destination)
                end_y = y
                end_x, end_y = validate_coordinates(end_x, end_y)
            except ValueError:
                console.print(format_error_message(f"Invalid coordinates: '{destination}' is not a valid X coordinate"))
                raise typer.Exit(1)
        else:
            # Single destination argument - parse as coordinates or named location
            parsed_dest = parse_destination(destination)

            if isinstance(parsed_dest, tuple):
                # Coordinates provided as "X Y"
                end_x, end_y = parsed_dest
                end_x, end_y = validate_coordinates(end_x, end_y)
            else:
                # Named location
                try:
                    end_x, end_y = resolve_named_location(parsed_dest, start_x, start_y)
                except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
                    console.print(format_error_message(f"Could not find location '{parsed_dest}': {e!s}"))
                    raise typer.Exit(1)

        # Calculate path
        path_result = calculate_path(start_x, start_y, end_x, end_y)

        # Display path information
        console.print(f"[bold cyan]Path for {character}[/bold cyan]")
        console.print(f"[dim]From: ({start_x}, {start_y}) → To: ({end_x}, {end_y})[/dim]")
        console.print(f"[dim]Summary: {path_result}[/dim]")
        console.print()

        if path_result.is_empty:
            console.print(format_success_message("Character is already at the destination"))
        else:
            console.print("[bold]Step-by-step path:[/bold]")
            for i, step in enumerate(path_result.steps, 1):
                console.print(f"  {i}. Move to {step}")

            console.print()
            console.print(f"[cyan]Total moves: {len(path_result.steps)}[/cyan]")
            console.print(f"[cyan]Total distance: {path_result.total_distance}[/cyan]")
            console.print(f"[cyan]Estimated time: ~{path_result.estimated_time} seconds[/cyan]")

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        console.print(format_error_message(f"Path calculation failed: {e!s}"))
        raise typer.Exit(1)


@app.command("batch")
def batch_action(
    character: str = typer.Argument(..., help="Character name"),
    action: str = typer.Argument(..., help="Action to repeat (gather, fight, rest)"),
    times: int = typer.Option(..., "--times", "-t", help="Number of times to repeat the action"),
    wait_cooldown: bool = typer.Option(False, "--wait-cooldown", "-w", help="Wait for cooldowns between actions"),
    continue_on_error: bool = typer.Option(
        False, "--continue-on-error", "-c", help="Continue on error instead of stopping"
    ),
) -> None:
    """Execute an action multiple times with progress tracking."""
    try:
        # Validate inputs
        character = validate_character_name(character)

        if action not in ACTION_EXECUTORS:
            console.print(
                format_error_message(
                    f"Invalid action '{action}'. Available actions: {', '.join(ACTION_EXECUTORS.keys())}"
                )
            )
            raise typer.Exit(1)

        if times <= 0:
            console.print(format_error_message("Number of times must be greater than 0"))
            raise typer.Exit(1)

        # Initialize results tracking
        results = BatchResults()
        action_executor = ACTION_EXECUTORS[action]

        console.print(f"[bold cyan]Starting batch {action} operation for {character}[/bold cyan]")
        console.print(
            f"[dim]Executing {times} times with {'cooldown waiting' if wait_cooldown else 'no cooldown waiting'}[/dim]"
        )
        console.print()

        # Create progress display
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TextColumn("•"),
            TextColumn("[progress.percentage]{task.completed}/{task.total}"),
            TextColumn("•"),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        ) as progress:
            task = progress.add_task(f"Executing {action} actions", total=times)

            for i in range(times):
                results.total_attempts += 1
                progress.update(task, description=f"Executing {action} action {i + 1}/{times}")

                # Execute the action
                cli_response = action_executor(character)

                if cli_response.success:
                    results.add_success(cli_response.data)

                    # Display action result
                    if (
                        action == "fight"
                        and cli_response.data
                        and isinstance(cli_response.data, dict)
                        and "fight" in cli_response.data
                    ):
                        console.print(format_combat_result(cli_response.data["fight"]))
                    elif (
                        action == "gather"
                        and cli_response.data
                        and isinstance(cli_response.data, dict)
                        and "details" in cli_response.data
                    ):
                        console.print(format_gathering_result(cli_response.data["details"]))
                    else:
                        console.print(
                            format_success_message(cli_response.message or f"{action.capitalize()} completed")
                        )

                elif cli_response.cooldown_remaining:
                    # Handle cooldown
                    cooldown_seconds = cli_response.cooldown_remaining
                    console.print(format_cooldown_message(cooldown_seconds))

                    if wait_cooldown:
                        console.print(
                            f"[blue]⏱ Waiting {format_time_duration(cooldown_seconds)} for cooldown...[/blue]"
                        )

                        # Wait with countdown - add 1 second for safety and handle float cooldowns
                        total_wait_seconds = math.ceil(cooldown_seconds) + 1
                        for remaining in range(total_wait_seconds, 0, -1):
                            progress.update(task, description=f"Waiting for cooldown: {remaining}s remaining")
                            time.sleep(1)

                        progress.update(task, description=f"Executing {action} action {i + 1}/{times}")
                        # Retry the action after cooldown
                        cli_response = action_executor(character)

                        if cli_response.success:
                            results.add_success(cli_response.data)

                            # Display action result
                            if (
                                action == "fight"
                                and cli_response.data
                                and isinstance(cli_response.data, dict)
                                and "fight" in cli_response.data
                            ):
                                console.print(format_combat_result(cli_response.data["fight"]))
                            elif (
                                action == "gather"
                                and cli_response.data
                                and isinstance(cli_response.data, dict)
                                and "details" in cli_response.data
                            ):
                                console.print(format_gathering_result(cli_response.data["details"]))
                            else:
                                console.print(
                                    format_success_message(
                                        cli_response.message or f"{action.capitalize()} completed"
                                    )
                                )
                        else:
                            error_msg = cli_response.error or "Action failed after cooldown"
                            results.add_failure(error_msg)
                            console.print(format_error_message(error_msg))

                            if not continue_on_error:
                                break
                    else:
                        # Don't wait for cooldown, treat as failure
                        error_msg = f"Action on cooldown for {format_time_duration(cooldown_seconds)}"
                        results.add_failure(error_msg)
                        console.print(format_error_message(error_msg))

                        if not continue_on_error:
                            break
                else:
                    # Handle other errors
                    error_msg = cli_response.error or "Action failed"
                    results.add_failure(error_msg)
                    console.print(format_error_message(error_msg))

                    if not continue_on_error:
                        break

                progress.advance(task)

                # Small delay between actions to avoid overwhelming the API
                if i < times - 1:
                    time.sleep(0.5)

        # Display final summary
        console.print()
        console.print(results.format_summary())

        # Exit with error code if there were failures and we're not continuing on error
        if results.failed_actions > 0 and not continue_on_error:
            raise typer.Exit(1)

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        console.print(format_error_message(f"Batch operation failed: {e!s}"))
        raise typer.Exit(1)

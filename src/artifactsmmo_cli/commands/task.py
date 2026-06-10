"""Task management commands."""

import httpx
import typer
from artifactsmmo_api_client.api.characters import get_character_characters_name_get
from artifactsmmo_api_client.api.my_characters import (
    action_accept_new_task_my_name_action_task_new_post,
    action_complete_task_my_name_action_task_complete_post,
    action_task_cancel_my_name_action_task_cancel_post,
    action_task_exchange_my_name_action_task_exchange_post,
    action_task_trade_my_name_action_task_trade_post,
)
from artifactsmmo_api_client.api.tasks import get_all_tasks_tasks_list_get, get_task_tasks_list_code_get
from artifactsmmo_api_client.errors import UnexpectedStatus
from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema
from artifactsmmo_api_client.models.skill import Skill
from artifactsmmo_api_client.models.task_type import TaskType
from artifactsmmo_api_client.types import UNSET, Unset
from rich.console import Console

from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.utils.api_display import display_field
from artifactsmmo_cli.utils.formatters import (
    format_cooldown_message,
    format_error_message,
    format_success_message,
    format_table,
)
from artifactsmmo_cli.utils.helpers import handle_api_error, handle_api_response
from artifactsmmo_cli.utils.validators import validate_character_name

app = typer.Typer(help="Task management commands")
console = Console()


@app.command("new")
def accept_new_task(character: str = typer.Argument(..., help="Character name")) -> None:
    """Accept a new task."""
    try:
        character = validate_character_name(character)

        client = ClientManager().client

        response = action_accept_new_task_my_name_action_task_new_post.sync(client=client, name=character)

        cli_response = handle_api_response(response, f"{character} accepted a new task")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "New task accepted"))
        else:
            console.print(format_error_message(cli_response.error or "Failed to accept task"))
            raise typer.Exit(1)

    except (ValueError, typer.BadParameter, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            error_msg = cli_response.error or str(e)
            # Add helpful context for location errors
            if "Wrong location for this action" in error_msg or "content not found at this location" in error_msg:
                error_msg += "\n💡 Hint: Task commands require your character to be at a Tasks Master location."
            console.print(format_error_message(error_msg))
        raise typer.Exit(1)


@app.command("complete")
def complete_task(character: str = typer.Argument(..., help="Character name")) -> None:
    """Complete current task."""
    try:
        character = validate_character_name(character)

        client = ClientManager().client

        response = action_complete_task_my_name_action_task_complete_post.sync(client=client, name=character)

        cli_response = handle_api_response(response, f"{character} completed task")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Task completed"))
        else:
            console.print(format_error_message(cli_response.error or "Failed to complete task"))
            raise typer.Exit(1)

    except (ValueError, typer.BadParameter, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            error_msg = cli_response.error or str(e)
            # Add helpful context for location errors
            if "Wrong location for this action" in error_msg or "content not found at this location" in error_msg:
                error_msg += "\n💡 Hint: Task commands require your character to be at a Tasks Master location."
            console.print(format_error_message(error_msg))
        raise typer.Exit(1)


@app.command("exchange")
def exchange_task(character: str = typer.Argument(..., help="Character name")) -> None:
    """Exchange current task for a new one."""
    try:
        character = validate_character_name(character)

        client = ClientManager().client

        response = action_task_exchange_my_name_action_task_exchange_post.sync(client=client, name=character)

        cli_response = handle_api_response(response, f"{character} exchanged task")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Task exchanged"))
        else:
            console.print(format_error_message(cli_response.error or "Failed to exchange task"))
            raise typer.Exit(1)

    except (ValueError, typer.BadParameter, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            error_msg = cli_response.error or str(e)
            # Add helpful context for location errors
            if "Wrong location for this action" in error_msg or "content not found at this location" in error_msg:
                error_msg += "\n💡 Hint: Task commands require your character to be at a Tasks Master location."
            console.print(format_error_message(error_msg))
        raise typer.Exit(1)


@app.command("trade")
def trade_task_items(
    character: str = typer.Argument(..., help="Character name"),
    item_code: str = typer.Argument(..., help="Item code to trade"),
    quantity: int = typer.Option(1, help="Quantity to trade"),
) -> None:
    """Trade task items with a Tasks Master."""
    try:
        character = validate_character_name(character)

        client = ClientManager().client

        # Create the item schema for the trade
        item_data = SimpleItemSchema(code=item_code, quantity=quantity)

        response = action_task_trade_my_name_action_task_trade_post.sync(client=client, name=character, body=item_data)

        cli_response = handle_api_response(response, f"{character} traded {quantity}x {item_code}")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or f"Traded {quantity}x {item_code}"))
        else:
            console.print(format_error_message(cli_response.error or "Failed to trade task items"))
            raise typer.Exit(1)

    except (ValueError, typer.BadParameter, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            error_msg = cli_response.error or str(e)
            # Add helpful context for location errors
            if "Wrong location for this action" in error_msg or "content not found at this location" in error_msg:
                error_msg += "\n💡 Hint: Task commands require your character to be at a Tasks Master location."
            console.print(format_error_message(error_msg))
        raise typer.Exit(1)


@app.command("cancel")
def cancel_task(character: str = typer.Argument(..., help="Character name")) -> None:
    """Cancel current task."""
    try:
        character = validate_character_name(character)

        client = ClientManager().client

        response = action_task_cancel_my_name_action_task_cancel_post.sync(client=client, name=character)

        cli_response = handle_api_response(response, f"{character} cancelled task")
        if cli_response.success:
            console.print(format_success_message(cli_response.message or "Task cancelled"))
        else:
            console.print(format_error_message(cli_response.error or "Failed to cancel task"))
            raise typer.Exit(1)

    except (ValueError, typer.BadParameter, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = handle_api_error(e)
        if cli_response.cooldown_remaining:
            console.print(format_cooldown_message(cli_response.cooldown_remaining))
        else:
            error_msg = cli_response.error or str(e)
            # Add helpful context for location errors
            if "Wrong location for this action" in error_msg or "content not found at this location" in error_msg:
                error_msg += "\n💡 Hint: Task commands require your character to be at a Tasks Master location."
            console.print(format_error_message(error_msg))
        raise typer.Exit(1)


@app.command("status")
def task_status(character: str = typer.Argument(..., help="Character name")) -> None:
    """Show current task status for a character."""
    try:
        character = validate_character_name(character)

        client = ClientManager().client

        # Get character information to see current task
        response = get_character_characters_name_get.sync(client=client, name=character)

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            character_data = cli_response.data

            # Check if character has a task using individual task fields
            task_code = getattr(character_data, "task", None)
            if task_code:
                headers = ["Property", "Value"]
                rows = [
                    ["Task Code", str(task_code)],
                    ["Task Type", str(display_field(character_data, "task_type"))],
                    [
                        "Progress",
                        f"{display_field(character_data, 'task_progress')}/"
                        f"{display_field(character_data, 'task_total')}",
                    ],
                ]

                output = format_table(headers, rows, title=f"{character}'s Current Task")
                console.print(output)

                # Try to get additional task details from the tasks API
                try:
                    task_details_response = get_task_tasks_list_code_get.sync(client=client, code=task_code)
                    task_details_cli_response = handle_api_response(task_details_response)

                    if task_details_cli_response.success and task_details_cli_response.data:
                        task_details = task_details_cli_response.data

                        # Show additional task information
                        detail_headers = ["Detail", "Value"]
                        detail_rows = []

                        if hasattr(task_details, "skill"):
                            detail_rows.append(["Required Skill", str(display_field(task_details, "skill"))])
                        if hasattr(task_details, "level"):
                            detail_rows.append(["Required Level", str(display_field(task_details, "level"))])
                        if hasattr(task_details, "description"):
                            detail_rows.append(["Description", str(display_field(task_details, "description"))])

                        if detail_rows:
                            detail_output = format_table(detail_headers, detail_rows, title="Task Details")
                            console.print()
                            console.print(detail_output)

                        # Show task rewards if available
                        if hasattr(task_details, "rewards") and task_details.rewards:
                            reward_headers = ["Reward", "Quantity"]
                            reward_rows = []
                            for reward in task_details.rewards:
                                if hasattr(reward, "code"):
                                    reward_rows.append(
                                        [
                                            str(display_field(reward, "code")),
                                            str(display_field(reward, "quantity")),
                                        ]
                                    )

                            if reward_rows:
                                reward_output = format_table(reward_headers, reward_rows, title="Task Rewards")
                                console.print()
                                console.print(reward_output)
                except (ValueError, UnexpectedStatus, httpx.HTTPError):
                    # If we can't get task details, that's okay - we still show the basic info
                    pass
            else:
                console.print(format_error_message(f"Character '{character}' has no active task"))
                raise typer.Exit(1)
        else:
            console.print(format_error_message(cli_response.error or f"Character '{character}' not found"))
            raise typer.Exit(1)

    except (ValueError, typer.BadParameter, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("list")
def list_tasks(
    task_type: str = typer.Option(None, help="Filter by task type"),
    skill: str = typer.Option(None, help="Filter by skill"),
    level: int = typer.Option(None, help="Filter by minimum level"),
    page: int = typer.Option(1, help="Page number"),
    size: int = typer.Option(50, help="Items per page"),
) -> None:
    """List available tasks."""
    try:
        client = ClientManager().client

        # Convert string parameters to enum values if provided
        skill_enum: Skill | Unset = UNSET
        if skill:
            try:
                skill_enum = Skill(skill.lower())
            except ValueError:
                console.print(format_error_message(f"Invalid skill: {skill}. Valid skills: {[s.value for s in Skill]}"))
                raise typer.Exit(1)

        task_type_enum: TaskType | Unset = UNSET
        if task_type:
            try:
                task_type_enum = TaskType(task_type.lower())
            except ValueError:
                console.print(
                    format_error_message(f"Invalid task type: {task_type}. Valid types: {[t.value for t in TaskType]}")
                )
                raise typer.Exit(1)

        level_param = UNSET if level is None else level

        response = get_all_tasks_tasks_list_get.sync(
            client=client, type_=task_type_enum, skill=skill_enum, min_level=level_param, page=page, size=size
        )

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            tasks = cli_response.data
            if hasattr(tasks, "data") and tasks.data:
                headers = ["Code", "Type", "Level", "Skill", "Rewards"]
                rows = []
                for task in tasks.data:
                    rewards = []
                    if hasattr(task, "rewards") and task.rewards:
                        for reward in task.rewards:
                            if hasattr(reward, "code"):
                                rewards.append(f"{display_field(reward, 'quantity')}x {reward.code}")

                    rows.append(
                        [
                            str(display_field(task, "code")),
                            str(display_field(task, "type")),
                            str(display_field(task, "level")),
                            str(display_field(task, "skill")),
                            ", ".join(rewards) if rewards else "None",
                        ]
                    )

                output = format_table(headers, rows, title="Available Tasks")
                console.print(output)
            else:
                console.print(format_error_message("No tasks found"))
        else:
            console.print(format_error_message(cli_response.error or "Could not retrieve tasks"))

    except (ValueError, typer.BadParameter, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)

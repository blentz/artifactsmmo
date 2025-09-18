# Product Requirements Prompt (PRP): ArtifactsMMO CLI Interface

## Goal
Build a comprehensive CLI/TUI interface for the ArtifactsMMO game that allows users to perform all available API actions through a user-friendly command-line interface. The interface should provide verb-noun based commands for intuitive interaction with the game API, supporting all character actions, bank operations, trading, and game management features.

## Why
- **User Impact**: Provides a powerful command-line interface for players who prefer terminal-based interaction with the game
- **Integration**: Leverages the existing artifactsmmo-api-client to provide full API coverage
- **Problems Solved**: Eliminates the need for manual API calls, provides auto-completion, help documentation, and a structured way to interact with all game features
- **Target Users**: Developers, power users, and automation enthusiasts who want programmatic control over their game characters

## What
A Python-based CLI/TUI application that:
- Provides verb-noun command structure (e.g., `move character`, `fight monster`, `craft item`)
- Supports all 77+ API endpoints available in the OpenAPI specification
- Handles authentication via TOKEN file
- Offers both simple CLI commands and an interactive TUI mode
- Provides comprehensive help, auto-completion, and error handling

### Success Criteria
- [ ] All API endpoints accessible through CLI commands
- [ ] Authentication working with TOKEN file
- [ ] Verb-noun command structure implemented
- [ ] Auto-completion support for commands and parameters
- [ ] Comprehensive help documentation for all commands
- [ ] Error handling with user-friendly messages
- [ ] Optional TUI mode for interactive use
- [ ] All tests passing with 100% coverage
- [ ] Zero mypy errors and ruff warnings

## All Needed Context

### Documentation & References
```yaml
# MUST READ - Include these in your context window
- url: https://docs.artifactsmmo.com/
  why: Official game documentation with API concepts, game mechanics, and examples

- url: https://api.artifactsmmo.com/docs/
  why: Interactive API documentation showing all endpoints and parameters

- url: https://typer.tiangolo.com/
  why: Typer documentation for building the CLI with type hints and auto-completion

- url: https://textual.textualize.io/
  why: Textual documentation for building the TUI interface

- url: https://click.palletsprojects.com/
  why: Click documentation (Typer is built on Click) for advanced CLI features

- file: /home/brett_lentz/git/artifactsmmo/openapi.json
  why: Complete OpenAPI specification with all endpoints, parameters, and schemas

- file: /home/brett_lentz/git/artifactsmmo/AGENTS.md
  why: Project-specific coding standards and requirements

- file: /home/brett_lentz/git/artifactsmmo/artifactsmmo-api-client/artifactsmmo_api_client/client.py
  why: API client implementation to understand how to interact with the API

- doc: https://github.com/tiangolo/typer#example
  section: Examples section showing command groups and subcommands
  critical: Shows how to create nested command structures for organizing API actions
```

### Current Codebase tree
```bash
/home/brett_lentz/git/artifactsmmo
├── AGENTS.md
├── generate_openapi_client.sh
├── LICENSE
├── NOTES.md
├── openapi_client_config.yml
├── openapi.json
├── pyproject.toml
├── README.md
├── TOKEN  # Authentication token file
├── artifactsmmo-api-client/  # Generated API client
│   ├── artifactsmmo_api_client/
│   │   ├── api/  # API endpoint modules
│   │   ├── models/  # Data models
│   │   ├── client.py  # Main client class
│   │   └── ...
│   └── ...
└── docs/
    └── PRP_artifactsmmo-cli.md  # This document
```

### Desired Codebase tree with files to be added
```bash
/home/brett_lentz/git/artifactsmmo
├── src/
│   ├── __init__.py
│   ├── artifactsmmo_cli/
│   │   ├── __init__.py
│   │   ├── main.py  # Entry point with Typer app
│   │   ├── config.py  # Configuration and token management
│   │   ├── client_manager.py  # API client wrapper
│   │   ├── commands/
│   │   │   ├── __init__.py
│   │   │   ├── character.py  # Character-related commands
│   │   │   ├── action.py  # Action commands (move, fight, gather, etc.)
│   │   │   ├── bank.py  # Bank operations
│   │   │   ├── trade.py  # Trading and Grand Exchange
│   │   │   ├── craft.py  # Crafting commands
│   │   │   ├── task.py  # Task management
│   │   │   ├── account.py  # Account management
│   │   │   └── info.py  # Information queries (items, monsters, maps, etc.)
│   │   ├── tui/
│   │   │   ├── __init__.py
│   │   │   ├── app.py  # Textual TUI application
│   │   │   ├── screens/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── main_screen.py  # Main TUI screen
│   │   │   │   ├── character_screen.py  # Character management screen
│   │   │   │   └── action_screen.py  # Action execution screen
│   │   │   └── widgets/
│   │   │       ├── __init__.py
│   │   │       └── status_bar.py  # Status display widget
│   │   ├── utils/
│   │   │   ├── __init__.py
│   │   │   ├── formatters.py  # Output formatting utilities
│   │   │   ├── validators.py  # Input validation
│   │   │   └── helpers.py  # Common helper functions
│   │   └── models/
│   │       ├── __init__.py
│   │       └── responses.py  # Response wrapper models
├── tests/
│   ├── __init__.py
│   ├── test_main.py
│   ├── test_config.py
│   ├── test_client_manager.py
│   ├── test_commands/
│   │   ├── __init__.py
│   │   ├── test_character.py
│   │   ├── test_action.py
│   │   └── ...
│   └── test_utils/
│       ├── __init__.py
│       └── test_formatters.py
└── docs/
    ├── PRP_artifactsmmo-cli.md
    └── CLI_USAGE.md  # User documentation
```

### Known Gotchas of our codebase & Library Quirks
```python
# CRITICAL: Project uses Python 3.13 with uv for dependency management
# Always use: uv run python, uv run pytest, etc.

# CRITICAL: One class per file rule - NEVER put multiple classes in same file
# Each class gets its own file named after the class (snake_case)

# CRITICAL: NO inline imports - all imports at top of file
# NO: from typing import TYPE_CHECKING or conditional imports

# CRITICAL: NO triple-dot imports
# BAD: from ...models import Something
# GOOD: from artifactsmmo_cli.models import Something

# CRITICAL: Authentication via TOKEN file
# Token must be read from ./TOKEN file in project root
# Format: single line with JWT token

# CRITICAL: API client is already generated
# Use artifactsmmo-api-client package, don't regenerate

# CRITICAL: Never catch Exception - be specific
# Use specific exception types for error handling

# CRITICAL: No print statements for fake success
# Actually implement and test functionality

# CRITICAL: Typer specifics
# - Use typer.Typer() app instance for command groups
# - Use @app.command() decorator for commands
# - Use type hints for automatic parameter parsing

# CRITICAL: Textual specifics for TUI
# - Textual apps are async
# - Use compose() method for widget layout
# - Handle keyboard shortcuts properly
```

## Implementation Blueprint

### CODE_STRUCTURE:
```
  .{PROJECT_ROOT}
  ├── docs/  # Documentation
  ├── tests/ # All tests
  ├── src/  # Application code
  │   └── artifactsmmo_cli/
  │       ├── commands/  # CLI command modules
  │       ├── tui/  # TUI interface
  │       ├── utils/  # Utilities
  │       └── models/  # Data models
  └── ...
```

### Data models and structure

```python
# src/artifactsmmo_cli/models/responses.py
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar('T')

class CLIResponse(BaseModel, Generic[T]):
    """Wrapper for API responses with CLI formatting"""
    success: bool
    data: Optional[T]
    error: Optional[str]
    message: Optional[str]

# src/artifactsmmo_cli/config.py
from pathlib import Path
from pydantic import BaseModel, Field

class Config(BaseModel):
    """CLI configuration"""
    token: str = Field(..., description="API authentication token")
    api_base_url: str = Field(default="https://api.artifactsmmo.com", description="API base URL")
    timeout: int = Field(default=30, description="API timeout in seconds")

    @classmethod
    def from_token_file(cls, token_path: Path = Path("TOKEN")) -> "Config":
        """Load config with token from file"""
        token = token_path.read_text().strip()
        return cls(token=token)
```

### List of tasks to be completed

```yaml
Task 1 - Setup Project Structure:
CREATE src/__init__.py:
  - Empty file for package initialization

CREATE src/artifactsmmo_cli/__init__.py:
  - Package initialization with version

CREATE src/artifactsmmo_cli/config.py:
  - Config class with token loading
  - API client configuration
  - PATTERN: Use pydantic for validation

Task 2 - Create Client Manager:
CREATE src/artifactsmmo_cli/client_manager.py:
  - Wrapper around artifactsmmo_api_client
  - Handle authentication headers
  - Manage client lifecycle
  - PATTERN: Singleton pattern for client instance

Task 3 - Main CLI Entry Point:
CREATE src/artifactsmmo_cli/main.py:
  - Initialize Typer app
  - Register command groups
  - Setup completion
  - Handle global options (--token, --debug)
  - PATTERN: Use typer.Typer() for main app

Task 4 - Character Commands:
CREATE src/artifactsmmo_cli/commands/character.py:
  - list: Show all characters
  - create: Create new character
  - delete: Delete character
  - select: Set active character
  - PATTERN: Use @app.command() decorators

Task 5 - Action Commands:
CREATE src/artifactsmmo_cli/commands/action.py:
  - move: Move character to coordinates
  - fight: Engage in combat
  - gather: Gather resources
  - rest: Rest to recover HP
  - equip/unequip: Manage equipment
  - use: Use items
  - PATTERN: Character name as first argument

Task 6 - Bank Commands:
CREATE src/artifactsmmo_cli/commands/bank.py:
  - deposit-gold: Deposit gold to bank
  - withdraw-gold: Withdraw gold from bank
  - deposit-item: Deposit items
  - withdraw-item: Withdraw items
  - list: Show bank contents
  - expand: Buy bank expansion

Task 7 - Trading Commands:
CREATE src/artifactsmmo_cli/commands/trade.py:
  - ge-buy: Buy from Grand Exchange
  - ge-sell: Sell on Grand Exchange
  - ge-orders: List current orders
  - ge-history: Show trade history
  - ge-cancel: Cancel order
  - give-gold: Give gold to another character
  - give-item: Give item to another character

Task 8 - Crafting Commands:
CREATE src/artifactsmmo_cli/commands/craft.py:
  - craft: Craft an item
  - recipes: List available recipes
  - recycle: Recycle items

Task 9 - Task Commands:
CREATE src/artifactsmmo_cli/commands/task.py:
  - new: Get new task
  - complete: Complete task
  - exchange: Exchange task
  - trade: Trade task items
  - cancel: Cancel task
  - list: Show current tasks

Task 10 - Information Commands:
CREATE src/artifactsmmo_cli/commands/info.py:
  - items: List/search items
  - monsters: List/search monsters
  - maps: Show map information
  - resources: List resource locations
  - achievements: Show achievements
  - leaderboard: Display leaderboards
  - events: Show current events

Task 11 - Account Commands:
CREATE src/artifactsmmo_cli/commands/account.py:
  - details: Show account details
  - change-password: Change password
  - logs: View account logs

Task 12 - Utility Functions:
CREATE src/artifactsmmo_cli/utils/formatters.py:
  - Format API responses for CLI output
  - Table formatting for lists
  - Color coding for different message types
  - PATTERN: Use rich library for formatting

CREATE src/artifactsmmo_cli/utils/validators.py:
  - Validate coordinates
  - Validate item codes
  - Validate quantities
  - PATTERN: Raise typer.BadParameter for invalid input

Task 13 - TUI Application (Optional Enhancement):
CREATE src/artifactsmmo_cli/tui/app.py:
  - Main Textual application
  - Navigation between screens
  - Real-time status updates
  - PATTERN: Use Textual's App class

Task 14 - Testing:
CREATE tests/test_config.py:
  - Test token loading
  - Test configuration validation

CREATE tests/test_client_manager.py:
  - Test client initialization
  - Test authentication

CREATE tests/test_commands/:
  - Test each command module
  - Mock API responses
  - Test error handling

Task 15 - Documentation:
CREATE docs/CLI_USAGE.md:
  - Command reference
  - Examples for each command
  - Configuration guide
```

### Per task pseudocode

```python
# Task 2 - Client Manager
# src/artifactsmmo_cli/client_manager.py
from artifactsmmo_api_client import Client
from artifactsmmo_api_client.types import Response
from typing import Optional
import httpx

class ClientManager:
    _instance: Optional["ClientManager"] = None
    _client: Optional[Client] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self, token: str, base_url: str = "https://api.artifactsmmo.com"):
        # Create httpx client with auth headers
        headers = {"Authorization": f"Bearer {token}"}
        httpx_client = httpx.Client(headers=headers, base_url=base_url)
        self._client = Client(base_url=base_url, httpx_client=httpx_client)

    @property
    def client(self) -> Client:
        if self._client is None:
            raise RuntimeError("Client not initialized. Call initialize() first.")
        return self._client

# Task 3 - Main CLI
# src/artifactsmmo_cli/main.py
import typer
from pathlib import Path
from artifactsmmo_cli.config import Config
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.commands import character, action, bank, trade

app = typer.Typer(
    name="artifactsmmo",
    help="CLI interface for ArtifactsMMO game",
    add_completion=True
)

# Register command groups
app.add_typer(character.app, name="character", help="Character management")
app.add_typer(action.app, name="action", help="Character actions")
app.add_typer(bank.app, name="bank", help="Bank operations")
app.add_typer(trade.app, name="trade", help="Trading operations")

@app.callback()
def main(
    token_file: Path = typer.Option(
        Path("TOKEN"),
        "--token-file",
        "-t",
        help="Path to token file"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug output")
):
    """Initialize the CLI with authentication"""
    try:
        config = Config.from_token_file(token_file)
        ClientManager().initialize(config.token, config.api_base_url)
    except FileNotFoundError:
        typer.echo("Error: TOKEN file not found", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error initializing client: {e}", err=True)
        raise typer.Exit(1)

# Task 4 - Character Commands
# src/artifactsmmo_cli/commands/character.py
import typer
from typing import Optional
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.utils.formatters import format_character_table

app = typer.Typer()

@app.command("list")
def list_characters():
    """List all your characters"""
    client = ClientManager().client
    # Use the my_characters API
    response = client.my_characters.get_my_characters_my_characters_get()

    if response:
        typer.echo(format_character_table(response.data))
    else:
        typer.echo("No characters found", err=True)

@app.command("create")
def create_character(
    name: str = typer.Argument(..., help="Character name"),
    skin: str = typer.Option("human1", help="Character skin")
):
    """Create a new character"""
    client = ClientManager().client
    # Call create character API
    # Handle response and errors
    pass

# Task 5 - Action Commands with character context
# src/artifactsmmo_cli/commands/action.py
@app.command("move")
def move_character(
    character: str = typer.Argument(..., help="Character name"),
    x: int = typer.Argument(..., help="X coordinate"),
    y: int = typer.Argument(..., help="Y coordinate")
):
    """Move character to coordinates"""
    client = ClientManager().client
    # PATTERN: All character actions need character name
    # Call: client.my_characters.action_move_my_name_action_move_post(
    #     name=character,
    #     destination=DestinationSchema(x=x, y=y)
    # )
    # Handle cooldown responses
    # Show remaining cooldown if action on cooldown
    pass
```

### Integration Points
```yaml
DEPENDENCIES:
  - add to: pyproject.toml
  - packages:
    - typer[all]  # CLI framework with completion
    - textual  # TUI framework
    - rich  # Terminal formatting
    - httpx  # Already included via api client

ENTRY POINT:
  - add to: pyproject.toml
  - [project.scripts]
  - artifactsmmo = "artifactsmmo_cli.main:app"

ENVIRONMENT:
  - TOKEN file in project root
  - Optional: ARTIFACTSMMO_TOKEN env variable as fallback

SHELL COMPLETION:
  - Typer auto-generates completion scripts
  - Install with: artifactsmmo --install-completion
```

## Validation Loop

### Level 1: Syntax & Style
```bash
# Run these FIRST - fix any errors before proceeding
uv run ruff check src/ --fix  # Auto-fix what's possible
uv run mypy src/              # Type checking

# Expected: No errors. If errors, READ the error and fix.
```

### Level 2: Unit Tests
```python
# tests/test_commands/test_character.py
import pytest
from typer.testing import CliRunner
from artifactsmmo_cli.main import app
from unittest.mock import patch, MagicMock

runner = CliRunner()

def test_list_characters_success():
    """Test listing characters"""
    with patch('artifactsmmo_cli.client_manager.ClientManager') as mock_cm:
        mock_response = MagicMock()
        mock_response.data = [{"name": "TestChar", "level": 10}]
        mock_cm().client.my_characters.get_my_characters_my_characters_get.return_value = mock_response

        result = runner.invoke(app, ["character", "list"])
        assert result.exit_code == 0
        assert "TestChar" in result.output

def test_move_character():
    """Test moving a character"""
    with patch('artifactsmmo_cli.client_manager.ClientManager') as mock_cm:
        result = runner.invoke(app, ["action", "move", "TestChar", "5", "10"])
        assert result.exit_code == 0
        # Verify API was called with correct parameters

def test_missing_token_file():
    """Test handling missing TOKEN file"""
    result = runner.invoke(app, ["--token-file", "nonexistent", "character", "list"])
    assert result.exit_code == 1
    assert "TOKEN file not found" in result.output
```

```bash
# Run and iterate until passing:
uv run pytest tests/ -v
# If failing: Read error, understand root cause, fix code, re-run
```

### Level 3: Integration Test
```bash
# Test with actual TOKEN file (if available)
echo "your-test-token" > TOKEN.test

# Test basic commands
uv run python -m artifactsmmo_cli.main --token-file TOKEN.test character list
uv run python -m artifactsmmo_cli.main --token-file TOKEN.test --help

# Test command completion
uv run python -m artifactsmmo_cli.main --install-completion
# Then test tab completion in shell

# Test TUI mode (if implemented)
uv run python -m artifactsmmo_cli.main tui
```

## Final Validation Checklist
- [ ] All tests pass: `uv run pytest tests/ -v --cov=src --cov-report=term-missing`
- [ ] No linting errors: `uv run ruff check src/`
- [ ] No type errors: `uv run mypy src/`
- [ ] CLI help works: `uv run python -m artifactsmmo_cli.main --help`
- [ ] All command groups accessible
- [ ] TOKEN file authentication working
- [ ] Error messages are user-friendly
- [ ] Tab completion installed and working
- [ ] Documentation complete and accurate

## Anti-Patterns to Avoid
- ❌ Don't hardcode API endpoints - use the generated client
- ❌ Don't skip error handling for API failures
- ❌ Don't use print() - use typer.echo() for output
- ❌ Don't put multiple classes in one file
- ❌ Don't use inline imports
- ❌ Don't catch generic Exception
- ❌ Don't mock API responses to pass tests - fix the actual issues
- ❌ Don't ignore cooldown responses from API
- ❌ Don't store sensitive data in code

## Bullshit Detector Score: 8/10

This PRP provides comprehensive context and clear implementation guidance. The score reflects:
- ✅ Specific documentation links and API references
- ✅ Clear file structure and responsibilities
- ✅ Concrete validation steps
- ✅ Project-specific coding standards included
- ✅ Realistic scope with optional TUI enhancement
- ⚠️ Could benefit from more specific API response examples
- ⚠️ Some implementation details left for developer discovery

The PRP is sufficiently detailed for an AI agent to implement a working CLI interface with proper error handling and testing.
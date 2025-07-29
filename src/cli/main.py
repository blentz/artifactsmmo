"""
CLI Main Entry Point

This module provides the main command-line interface for the ArtifactsMMO AI Player.
It handles argument parsing, command routing, and integrates with all system components
including character management, AI player control, and diagnostic commands.

The CLI supports character CRUD operations, AI player lifecycle management,
and comprehensive diagnostic tools for troubleshooting GOAP planning and state management.
"""

import argparse
import asyncio
import logging
import random
import string
import sys
from typing import Any

import src.lib.log as log_module

from ..ai_player.ai_player import AIPlayer
from ..ai_player.action_executor import ActionExecutor
from ..ai_player.actions import ActionRegistry
from ..ai_player.goal_manager import GoalManager
from ..ai_player.state.state_manager import StateManager
from ..game_data.api_client import APIClientWrapper
from ..game_data.cache_manager import CacheManager
from ..lib.log import LogManager
from .commands.diagnostics import DiagnosticCommands


def generate_random_character_name() -> str:
    """Generate random character name with format ([a-zA-Z0-9_-]{6,10}).
    
    Parameters:
        None
        
    Return values:
        String containing randomized character name matching API requirements
        
    This function generates a random character name using alphanumeric characters,
    underscores, and hyphens with a length between 6-10 characters
    as required by the ArtifactsMMO API validation rules.
    """
    # Characters allowed by API: alphanumeric, underscore, hyphen (no periods)
    allowed_chars = string.ascii_letters + string.digits + '_-'
    
    # Random length between 6 and 10 characters
    name_length = random.randint(6, 10)
    
    # Generate random name
    random_name = ''.join(random.choice(allowed_chars) for _ in range(name_length))
    
    return random_name


class CLIManager:
    """Main CLI manager that coordinates all command operations"""

    def __init__(self):
        """Initialize CLI manager for command coordination.
        
        Parameters:
            None
            
        Return values:
            None (constructor)
            
        This constructor initializes the CLI manager that coordinates all
        command-line operations including character management, AI player
        control, and diagnostic commands for the ArtifactsMMO AI Player.
        """
        self.log_manager = LogManager()
        self.api_client: APIClientWrapper | None = None
        self.diagnostic_commands = DiagnosticCommands()
        self.running_players: dict[str, AIPlayer] = {}
        self.logger = logging.getLogger("cli.manager")

    def _initialize_diagnostic_components(self, token_file: str) -> DiagnosticCommands:
        """Initialize all components required for diagnostics.
        
        Parameters:
            token_file: Path to API token file
            
        Return values:
            Fully initialized DiagnosticCommands instance
            
        This method ensures all required components (APIClientWrapper, ActionRegistry,
        GoalManager) are properly initialized and available for diagnostic operations.
        These components are essential - if any fail to initialize, it's a system bug
        that should crash immediately.
        """
        if not self.api_client:
            self.api_client = APIClientWrapper(token_file)

        # Initialize required components - these MUST work or it's a system bug
        cache_manager = CacheManager(self.api_client)
        action_registry = ActionRegistry()
        goal_manager = GoalManager(action_registry, self.api_client.cooldown_manager)
        
        return DiagnosticCommands(
            action_registry=action_registry,
            goal_manager=goal_manager,
            api_client=self.api_client
        )

    def create_parser(self) -> argparse.ArgumentParser:
        """Create argument parser with all command groups.
        
        Parameters:
            None
            
        Return values:
            ArgumentParser configured with all CLI commands and options
            
        This method creates and configures the main argument parser with
        all subcommands for character management, AI player control, and
        diagnostic operations, including global options like logging levels.
        """
        parser = argparse.ArgumentParser(
            description="ArtifactsMMO AI Player - Autonomous character control system",
            formatter_class=argparse.RawDescriptionHelpFormatter
        )

        # Global options
        parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default="INFO",
            help="Set logging level (default: INFO)"
        )
        parser.add_argument(
            "--token-file",
            default="TOKEN",
            help="Path to file containing ArtifactsMMO API token (default: TOKEN)"
        )

        # Create subparsers for command groups
        subparsers = parser.add_subparsers(dest="command", help="Available commands")

        # Setup command groups
        self.setup_character_commands(subparsers)
        self.setup_ai_player_commands(subparsers)
        self.setup_diagnostic_commands(subparsers)

        return parser

    def setup_character_commands(self, subparsers) -> None:
        """Setup character management commands.
        
        Parameters:
            subparsers: Subparser group for adding character commands
            
        Return values:
            None (modifies subparsers)
            
        This method configures all character-related CLI commands including
        create-character, delete-character, and list-characters with their
        respective arguments and validation requirements.
        """
        # Create character command
        create_parser = subparsers.add_parser(
            "create-character",
            help="Create a new character"
        )
        create_parser.add_argument(
            "skin",
            choices=["men1", "men2", "men3", "women1", "women2", "women3"],
            help="Character skin/appearance"
        )
        create_parser.add_argument(
            "--name",
            help="Character name (3-12 characters, alphanumeric and underscore only). If not provided, a random name will be generated."
        )
        create_parser.set_defaults(func=self.handle_create_character)

        # Delete character command
        delete_parser = subparsers.add_parser(
            "delete-character",
            help="Delete an existing character"
        )
        delete_parser.add_argument(
            "name",
            help="Character name to delete"
        )
        delete_parser.add_argument(
            "--confirm",
            action="store_true",
            help="Skip confirmation prompt"
        )
        delete_parser.set_defaults(func=self.handle_delete_character)

        # List characters command
        list_parser = subparsers.add_parser(
            "list-characters",
            help="List all characters on the account"
        )
        list_parser.add_argument(
            "--detailed",
            action="store_true",
            help="Show detailed character information"
        )
        list_parser.set_defaults(func=self.handle_list_characters)

        # Load game data command
        load_data_parser = subparsers.add_parser(
            "load-data",
            help="Load and cache all game data from API"
        )
        load_data_parser.add_argument(
            "--force",
            action="store_true",
            help="Force refresh all cached data"
        )
        load_data_parser.add_argument(
            "--data-type",
            choices=["all", "items", "monsters", "maps", "resources", "npcs", "characters"],
            default="all",
            help="Specific data type to load (default: all)"
        )
        load_data_parser.add_argument(
            "--init",
            action="store_true",
            help="Initialize all game data for first-time setup"
        )
        load_data_parser.set_defaults(func=self.handle_load_data)

    def setup_ai_player_commands(self, subparsers) -> None:
        """Setup AI player control commands.
        
        Parameters:
            subparsers: Subparser group for adding AI player commands
            
        Return values:
            None (modifies subparsers)
            
        This method configures all AI player control CLI commands including
        run-character, stop-character, and status-character with their
        respective arguments and operational parameters.
        """
        # Run character command
        run_parser = subparsers.add_parser(
            "run-character",
            help="Start autonomous AI player for a character"
        )
        run_parser.add_argument(
            "name",
            help="Character name to run autonomously"
        )
        run_parser.add_argument(
            "--goal",
            help="Specific goal to pursue (optional)"
        )
        run_parser.add_argument(
            "--max-runtime",
            type=int,
            help="Maximum runtime in minutes (optional)"
        )
        run_parser.add_argument(
            "--save-interval",
            type=int,
            default=300,
            help="State save interval in seconds (default: 300)"
        )
        run_parser.set_defaults(func=self.handle_run_character)

        # Stop character command
        stop_parser = subparsers.add_parser(
            "stop-character",
            help="Stop autonomous AI player for a character"
        )
        stop_parser.add_argument(
            "name",
            help="Character name to stop"
        )
        stop_parser.add_argument(
            "--force",
            action="store_true",
            help="Force immediate stop without graceful shutdown"
        )
        stop_parser.set_defaults(func=self.handle_stop_character)

        # Character status command
        status_parser = subparsers.add_parser(
            "status-character",
            help="Show character and AI player status"
        )
        status_parser.add_argument(
            "name",
            help="Character name to check status"
        )
        status_parser.add_argument(
            "--monitor",
            action="store_true",
            help="Continuous monitoring mode"
        )
        status_parser.set_defaults(func=self.handle_character_status)

    def setup_diagnostic_commands(self, subparsers) -> None:
        """Setup diagnostic and troubleshooting commands.
        
        Parameters:
            subparsers: Subparser group for adding diagnostic commands
            
        Return values:
            None (modifies subparsers)
            
        This method configures comprehensive diagnostic CLI commands including
        state inspection, action analysis, GOAP planning visualization, and
        system configuration troubleshooting for AI player debugging.
        """
        # Diagnose state command
        state_parser = subparsers.add_parser(
            "diagnose-state",
            help="Diagnose character state and validation"
        )
        state_parser.add_argument(
            "name",
            help="Character name to diagnose"
        )
        state_parser.add_argument(
            "--validate-enum",
            action="store_true",
            help="Perform GameState enum validation"
        )
        state_parser.set_defaults(func=self.handle_diagnose_state)

        # Diagnose actions command
        actions_parser = subparsers.add_parser(
            "diagnose-actions",
            help="Diagnose available actions and properties"
        )
        actions_parser.add_argument(
            "--character",
            help="Character name for state-specific analysis"
        )
        actions_parser.add_argument(
            "--show-costs",
            action="store_true",
            help="Include GOAP action costs in output"
        )
        actions_parser.add_argument(
            "--list-all",
            action="store_true",
            help="List all actions regardless of character state"
        )
        actions_parser.add_argument(
            "--show-preconditions",
            action="store_true",
            help="Display action preconditions and effects"
        )
        actions_parser.set_defaults(func=self.handle_diagnose_actions)

        # Diagnose planning command
        plan_parser = subparsers.add_parser(
            "diagnose-plan",
            help="Diagnose GOAP planning process"
        )
        plan_parser.add_argument(
            "name",
            help="Character name for planning analysis"
        )
        plan_parser.add_argument(
            "goal",
            help="Goal to analyze planning for"
        )
        plan_parser.add_argument(
            "--verbose",
            action="store_true",
            help="Include detailed planning algorithm steps"
        )
        plan_parser.add_argument(
            "--show-steps",
            action="store_true",
            help="Display each step in the generated plan"
        )
        plan_parser.set_defaults(func=self.handle_diagnose_plan)

        # Test planning command
        test_parser = subparsers.add_parser(
            "test-planning",
            help="Test planning with mock scenarios"
        )
        test_parser.add_argument(
            "--mock-state-file",
            help="Path to JSON file containing mock character state"
        )
        test_parser.add_argument(
            "--start-level",
            type=int,
            help="Starting character level for simulation"
        )
        test_parser.add_argument(
            "--goal-level",
            type=int,
            help="Target level for planning simulation"
        )
        test_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate without API calls"
        )
        test_parser.set_defaults(func=self.handle_test_planning)

        # Diagnose weights command
        weights_parser = subparsers.add_parser(
            "diagnose-weights",
            help="Diagnose action weights and GOAP configuration"
        )
        weights_parser.add_argument(
            "--show-action-costs",
            action="store_true",
            help="Display detailed action cost breakdowns"
        )
        weights_parser.set_defaults(func=self.handle_diagnose_weights)

        # Diagnose cooldowns command
        cooldowns_parser = subparsers.add_parser(
            "diagnose-cooldowns",
            help="Diagnose cooldown management and timing"
        )
        cooldowns_parser.add_argument(
            "name",
            help="Character name to monitor cooldown status"
        )
        cooldowns_parser.add_argument(
            "--monitor",
            action="store_true",
            help="Provide continuous cooldown monitoring"
        )
        cooldowns_parser.set_defaults(func=self.handle_diagnose_cooldowns)

    async def handle_create_character(self, args) -> None:
        """Handle character creation command.
        
        Parameters:
            args: Parsed command arguments containing character name and skin
            
        Return values:
            None (async operation)
            
        This method processes the create-character command by validating input
        parameters, calling the API client to create the character, and providing
        user feedback on success or failure. If no name is provided, generates
        a random name matching the format ([a-zA-Z0-9_-.]{6,10}).
        """
        try:
            if not self.api_client:
                self.api_client = APIClientWrapper(args.token_file)

            # Generate random name if not provided
            character_name = args.name
            if not character_name:
                character_name = generate_random_character_name()
                print(f"Generated random character name: {character_name}")

            # Validate character name
            if not (3 <= len(character_name) <= 12):
                print("Error: Character name must be 3-12 characters long")
                return

            # Updated validation to match API requirements: alphanumeric, underscore, hyphen only
            allowed_chars = set(string.ascii_letters + string.digits + '_-')
            if not all(c in allowed_chars for c in character_name):
                print("Error: Character name can only contain alphanumeric characters, underscores, and hyphens")
                return

            print(f"Creating character '{character_name}' with skin '{args.skin}'...")

            character = await self.api_client.create_character(character_name, args.skin)

            print(f"✓ Character '{character.name}' created successfully!")
            print(f"  Level: {character.level}")
            print(f"  Location: {character.x}, {character.y}")
            print(f"  Skin: {character.skin}")

        except Exception as e:
            self.logger.error(f"Failed to create character: {e}")
            print(f"Error creating character: {e}")

    async def handle_delete_character(self, args) -> None:
        """Handle character deletion command.
        
        Parameters:
            args: Parsed command arguments containing character name to delete
            
        Return values:
            None (async operation)
            
        This method processes the delete-character command by confirming the
        deletion request, calling the API client to remove the character, and
        cleaning up associated data files.
        """
        try:
            if not self.api_client:
                self.api_client = APIClientWrapper(args.token_file)

            # Confirmation prompt (unless --confirm flag is used)
            if not args.confirm:
                response = input(f"Are you sure you want to delete character '{args.name}'? (y/N): ")
                if response.lower() not in ['y', 'yes']:
                    print("Character deletion cancelled.")
                    return

            print(f"Deleting character '{args.name}'...")

            success = await self.api_client.delete_character(args.name)

            if success:
                print(f"✓ Character '{args.name}' deleted successfully!")

                # Initialize cache manager to clear character cache
                cache_manager = CacheManager(self.api_client)
                cache_manager.clear_cache("characters")

                # Clean up any local character data if running
                if args.name in self.running_players:
                    print("Stopping AI player for deleted character...")
                    del self.running_players[args.name]

            else:
                print(f"Failed to delete character '{args.name}'")

        except Exception as e:
            self.logger.error(f"Failed to delete character: {e}")
            print(f"Error deleting character: {e}")

    async def handle_list_characters(self, args) -> None:
        """Handle character listing command.
        
        Parameters:
            args: Parsed command arguments for listing options
            
        Return values:
            None (async operation)
            
        This method processes the list-characters command by retrieving all
        user characters from the cache manager and displaying their information
        in a formatted table with levels, locations, and status.
        """
        try:
            if not self.api_client:
                self.api_client = APIClientWrapper(args.token_file)

            # Initialize cache manager
            cache_manager = CacheManager(self.api_client)

            print("Retrieving characters...")

            # Use cache manager to get characters (will cache for future use)
            characters = await cache_manager.cache_all_characters()

            if not characters:
                print("No characters found on this account.")
                print(f"Character data cached in: data/characters.yaml")
                return

            print(f"\nFound {len(characters)} character(s):")
            print("-" * 60)

            for char in characters:
                ai_status = "Running" if char['name'] in self.running_players else "Stopped"

                if args.detailed:
                    print(f"Name: {char['name']}")
                    print(f"  Level: {char['level']}")
                    print(f"  Location: ({char['x']}, {char['y']})")
                    print(f"  Skin: {char['skin']}")
                    print(f"  HP: {char['hp']}/{char['max_hp']}")
                    print(f"  Gold: {char['gold']}")
                    print(f"  AI Status: {ai_status}")
                    print("-" * 60)
                else:
                    print(f"{char['name']:<15} Lv.{char['level']:<3} ({char['x']:>3},{char['y']:>3}) {ai_status}")

            print(f"\nCharacter data cached in: data/characters.yaml")

        except Exception as e:
            self.logger.error(f"Failed to list characters: {e}")
            print(f"Error listing characters: {e}")

    async def handle_load_data(self, args) -> None:
        """Handle game data loading command.
        
        Parameters:
            args: Parsed command arguments for data loading options
            
        Return values:
            None (async operation)
            
        This method loads and caches all game data from the API including
        items, monsters, maps, resources, NPCs, and characters for offline
        access by the AI player system.
        """
        try:
            if not self.api_client:
                self.api_client = APIClientWrapper(args.token_file)

            # Initialize cache manager
            cache_manager = CacheManager(self.api_client)

            if args.init:
                print("Initializing all game data for first-time setup...")
                print("This will load all game data types and may take a moment...")
                # Force refresh when initializing
                force_refresh = True
                data_types_to_load = ["items", "monsters", "maps", "resources", "npcs", "characters"]
            else:
                print("Loading game data from API...")
                force_refresh = args.force
                if args.data_type == "all":
                    data_types_to_load = ["items", "monsters", "maps", "resources", "npcs", "characters"]
                else:
                    data_types_to_load = [args.data_type]

            for data_type in data_types_to_load:
                print(f"Loading {data_type}...")
                
                try:
                    if data_type == "items":
                        items = await cache_manager.get_all_items(force_refresh=force_refresh)
                        print(f"✓ Cached {len(items)} items in data/items.yaml")
                    
                    elif data_type == "monsters":
                        monsters = await cache_manager.get_all_monsters(force_refresh=force_refresh)
                        print(f"✓ Cached {len(monsters)} monsters in data/monsters.yaml")
                    
                    elif data_type == "maps":
                        maps = await cache_manager.get_all_maps(force_refresh=force_refresh)
                        print(f"✓ Cached {len(maps)} maps in data/maps.yaml")
                    
                    elif data_type == "resources":
                        resources = await cache_manager.get_all_resources(force_refresh=force_refresh)
                        print(f"✓ Cached {len(resources)} resources in data/resources.yaml")
                    
                    elif data_type == "npcs":
                        npcs = await cache_manager.get_all_npcs(force_refresh=force_refresh)
                        print(f"✓ Cached {len(npcs)} NPCs in data/npcs.yaml")
                    
                    elif data_type == "characters":
                        characters = await cache_manager.cache_all_characters(force_refresh=force_refresh)
                        print(f"✓ Cached {len(characters)} characters in data/characters.yaml")
                        
                except Exception as e:
                    self.logger.error(f"Failed to load {data_type}: {e}")
                    print(f"✗ Error loading {data_type}: {e}")

            if args.init:
                print(f"\n🎉 Game data initialization complete!")
                print(f"All game data has been cached and is ready for use.")
                print(f"Cache files location: data/ directory")
                print(f"\nAvailable data files:")
                print(f"  - data/characters.yaml (your characters)")
                print(f"  - data/items.yaml (all game items)")
                print(f"  - data/monsters.yaml (all monsters)")
                print(f"  - data/maps.yaml (all map locations)")
                print(f"  - data/resources.yaml (all gatherable resources)")
                print(f"  - data/npcs.yaml (all NPCs and traders)")
                print(f"  - data/metadata.yaml (cache management)")
            else:
                print(f"\nGame data loading complete!")
                print(f"All cached data is stored in the 'data/' directory")

        except Exception as e:
            # Let specific exceptions bubble up - don't mask errors with generic handling
            print(f"Failed to load game data: {e}")
            raise

    async def handle_run_character(self, args) -> None:
        """Handle AI player run command.
        
        Parameters:
            args: Parsed command arguments containing character name and options
            
        Return values:
            None (async operation)
            
        This method starts the autonomous AI player for the specified character,
        initializing all systems, beginning the main game loop, and providing
        real-time status updates during operation.
        """
        try:
            if args.name in self.running_players:
                print(f"AI player for '{args.name}' is already running.")
                return

            if not self.api_client:
                self.api_client = APIClientWrapper(args.token_file)

            print(f"Starting AI player for character '{args.name}'...")

            # Initialize AI player
            ai_player = AIPlayer(args.name)

            # Create component dependencies
            cache_manager = CacheManager(self.api_client)
            state_manager = StateManager(args.name, self.api_client, cache_manager)
            action_registry = ActionRegistry()
            goal_manager = GoalManager(action_registry, self.api_client.cooldown_manager)
            action_executor = ActionExecutor(self.api_client, self.api_client.cooldown_manager)

            # Initialize AI player dependencies
            ai_player.initialize_dependencies(state_manager, goal_manager, action_executor, action_registry)

            # TODO: Set specific goal if provided
            if args.goal:
                print(f"Setting goal: {args.goal}")

            # Track the running player
            self.running_players[args.name] = ai_player

            print(f"✓ AI player for '{args.name}' started successfully!")
            print(f"  Goal: {args.goal or 'Auto-select optimal goals'}")
            print(f"  Save interval: {args.save_interval} seconds")
            if args.max_runtime:
                print(f"  Max runtime: {args.max_runtime} minutes")

            # Start the AI player main loop
            try:
                await ai_player.start()
            except KeyboardInterrupt:
                print("\nReceived interrupt signal, stopping AI player...")
                await ai_player.stop()
            finally:
                # Clean up
                if args.name in self.running_players:
                    del self.running_players[args.name]
                print(f"AI player for '{args.name}' stopped.")

        except Exception as e:
            # Clean up on error then let exception bubble up
            if args.name in self.running_players:
                del self.running_players[args.name]
            raise

    async def handle_stop_character(self, args) -> None:
        """Handle AI player stop command.
        
        Parameters:
            args: Parsed command arguments containing character name to stop
            
        Return values:
            None (async operation)
            
        This method gracefully stops the autonomous AI player for the specified
        character, saving current state, completing ongoing actions, and providing
        confirmation of successful shutdown.
        """
        try:
            if args.name not in self.running_players:
                print(f"AI player for '{args.name}' is not currently running.")
                return

            ai_player = self.running_players[args.name]

            if args.force:
                print(f"Force stopping AI player for '{args.name}'...")
                # Force immediate stop
                del self.running_players[args.name]
                print(f"✓ AI player for '{args.name}' force stopped.")
            else:
                print(f"Gracefully stopping AI player for '{args.name}'...")

                # Request graceful shutdown
                await ai_player.stop()

                # Remove from running players
                del self.running_players[args.name]

                print(f"✓ AI player for '{args.name}' stopped gracefully.")

        except Exception as e:
            self.logger.error(f"Failed to stop AI player: {e}")
            print(f"Error stopping AI player: {e}")
            # Force cleanup on error
            if args.name in self.running_players:
                del self.running_players[args.name]

    async def handle_character_status(self, args) -> None:
        """Handle character status command.
        
        Parameters:
            args: Parsed command arguments containing character name for status query
            
        Return values:
            None (async operation)
            
        This method retrieves and displays comprehensive character status including
        current level, location, equipment, active goals, and AI player operational
        status for monitoring and debugging purposes.
        """
        try:
            if not self.api_client:
                self.api_client = APIClientWrapper(args.token_file)

            print(f"Retrieving status for character '{args.name}'...")

            # Get character data from API
            characters = await self.api_client.get_characters()
            character = next((c for c in characters if c.get('name') == args.name), None)

            if not character:
                print(f"Character '{args.name}' not found.")
                return

            print(f"\n=== Character Status: {args.name} ===")
            print(f"Level: {character['level']}")
            print(f"Location: ({character['x']}, {character['y']})")
            print(f"HP: {character['hp']}/{character['max_hp']}")
            print(f"Gold: {character['gold']}")
            print(f"Skin: {character['skin']}")

            # AI Player status
            if args.name in self.running_players:
                ai_player = self.running_players[args.name]
                print("\n=== AI Player Status ===")
                print("Status: Running")
                # TODO: Add more AI player status details when available
                # print(f"Current Goal: {ai_player.current_goal}")
                # print(f"Current Action: {ai_player.current_action}")

                if args.monitor:
                    print("\n=== Monitoring Mode (Ctrl+C to exit) ===")
                    try:
                        while True:
                            await asyncio.sleep(5)
                            # TODO: Update with real-time status
                            print(f"[{asyncio.get_event_loop().time():.0f}] Character still running...")
                    except KeyboardInterrupt:
                        print("\nMonitoring stopped.")
            else:
                print("\n=== AI Player Status ===")
                print("Status: Stopped")

        except Exception as e:
            self.logger.error(f"Failed to get character status: {e}")
            print(f"Error getting character status: {e}")

    async def handle_diagnose_state(self, args) -> None:
        """Handle state diagnostic command.
        
        Parameters:
            args: Parsed command arguments containing character name and diagnostic options
            
        Return values:
            None (async operation)
            
        This method executes comprehensive character state diagnostics including
        GameState enum validation, state consistency checking, and detailed
        analysis for troubleshooting state management issues.
        """
        try:
            # Initialize all diagnostic components - these MUST work or it's a bug
            diagnostic_commands = self._initialize_diagnostic_components(args.token_file)
            
            print(f"Running state diagnostics for character '{args.name}'...")

            result = await diagnostic_commands.diagnose_state(
                args.name,
                validate_enum=args.validate_enum
            )

            # Format and display the diagnostic results
            output = diagnostic_commands.format_state_output(result)
            print(output)

        except Exception as e:
            self.logger.error(f"Failed to diagnose state: {e}")
            print(f"Error running state diagnostics: {e}")

    async def handle_diagnose_actions(self, args) -> None:
        """Handle action diagnostic command.
        
        Parameters:
            args: Parsed command arguments containing diagnostic options and filters
            
        Return values:
            None (async operation)
            
        This method analyzes available actions including preconditions, effects,
        costs, and executability for troubleshooting GOAP planning and action
        availability issues in the AI player system.
        """
        try:
            # Initialize all diagnostic components - these MUST work or it's a bug
            diagnostic_commands = self._initialize_diagnostic_components(args.token_file)
            
            print("Running action diagnostics...")

            result = await diagnostic_commands.diagnose_actions(
                character_name=args.character,
                show_costs=args.show_costs,
                list_all=args.list_all,
                show_preconditions=args.show_preconditions
            )

            # Format and display the diagnostic results
            output = diagnostic_commands.format_action_output(result)
            print(output)

        except Exception as e:
            self.logger.error(f"Failed to diagnose actions: {e}")
            print(f"Error running action diagnostics: {e}")

    async def handle_diagnose_plan(self, args) -> None:
        """Handle planning diagnostic command.
        
        Parameters:
            args: Parsed command arguments containing character name, goal, and verbosity options
            
        Return values:
            None (async operation)
            
        This method provides detailed analysis of GOAP planning processes including
        step-by-step visualization, optimization insights, and troubleshooting
        guidance for planning algorithm performance.
        """
        try:
            # Initialize all diagnostic components - these MUST work or it's a bug
            diagnostic_commands = self._initialize_diagnostic_components(args.token_file)
            
            print(f"Running planning diagnostics for character '{args.name}' with goal '{args.goal}'...")

            result = await diagnostic_commands.diagnose_plan(
                args.name,
                args.goal,
                verbose=args.verbose,
                show_steps=args.show_steps
            )

            # Format and display the diagnostic results
            output = diagnostic_commands.format_planning_output(result)
            print(output)

        except Exception as e:
            self.logger.error(f"Failed to diagnose planning: {e}")
            print(f"Error running planning diagnostics: {e}")

    async def handle_test_planning(self, args) -> None:
        """Handle planning simulation command.
        
        Parameters:
            args: Parsed command arguments containing simulation parameters and scenarios
            
        Return values:
            None (async operation)
            
        This method executes GOAP planning simulations using mock scenarios
        and test data to validate planning algorithms without requiring live
        character data or API interactions.
        """
        try:
            # Initialize all diagnostic components - these MUST work or it's a bug
            diagnostic_commands = self._initialize_diagnostic_components(args.token_file)
            
            print("Running planning simulation tests...")

            result = await diagnostic_commands.test_planning(
                mock_state_file=args.mock_state_file,
                start_level=args.start_level,
                goal_level=args.goal_level,
                dry_run=args.dry_run
            )

            # Display the test results
            print("=== Planning Test Results ===")
            for key, value in result.items():
                print(f"{key}: {value}")

        except Exception as e:
            self.logger.error(f"Failed to test planning: {e}")
            print(f"Error running planning tests: {e}")

    async def handle_diagnose_weights(self, args) -> None:
        """Handle weight diagnostics command.
        
        Parameters:
            args: Parsed command arguments containing diagnostic options
            
        Return values:
            None (async operation)
            
        This method executes GOAP weight and configuration diagnostics to identify
        optimization opportunities, validate weight balance, and ensure effective
        planning performance for the AI player system.
        """
        try:
            # Initialize all diagnostic components - these MUST work or it's a bug
            diagnostic_commands = self._initialize_diagnostic_components(args.token_file)
            
            print("Running weight and configuration diagnostics...")

            result = await diagnostic_commands.diagnose_weights(
                show_action_costs=args.show_action_costs
            )

            # Format and display the diagnostic results
            output = self.format_weights_output(result)
            print(output)

        except Exception as e:
            self.logger.error(f"Failed to diagnose weights: {e}")
            print(f"Error running weight diagnostics: {e}")

    async def handle_diagnose_cooldowns(self, args) -> None:
        """Handle cooldown diagnostics command.
        
        Parameters:
            args: Parsed command arguments containing character name and monitoring options
            
        Return values:
            None (async operation)
            
        This method executes cooldown management diagnostics to analyze timing
        accuracy, API compliance, and cooldown prediction for troubleshooting
        timing issues and ensuring proper action execution scheduling.
        """
        try:
            # Initialize all diagnostic components - these MUST work or it's a bug
            diagnostic_commands = self._initialize_diagnostic_components(args.token_file)
            
            print(f"Running cooldown diagnostics for character '{args.name}'...")

            result = await diagnostic_commands.diagnose_cooldowns(
                args.name,
                monitor=args.monitor
            )

            # Format and display the diagnostic results
            output = self.format_cooldowns_output(result)
            print(output)

        except Exception as e:
            self.logger.error(f"Failed to diagnose cooldowns: {e}")
            print(f"Error running cooldown diagnostics: {e}")

    def format_weights_output(self, weights_data: dict[str, Any]) -> str:
        """Format weight analysis for CLI display.
        
        Parameters:
            weights_data: Dictionary containing weight analysis and configuration data
            
        Return values:
            Formatted string representation suitable for CLI output
            
        This method formats GOAP weight analysis into a readable format for CLI
        display, showing cost distributions, optimization opportunities, and
        configuration validation results for debugging planning performance.
        """
        lines = []
        lines.append("=== WEIGHT & CONFIGURATION ANALYSIS ===")
        
        # Configuration validation
        config_valid = weights_data.get("configuration_validation", {}).get("valid", True)
        lines.append(f"Configuration valid: {config_valid}")
        
        warnings = weights_data.get("configuration_validation", {}).get("warnings", [])
        errors = weights_data.get("configuration_validation", {}).get("errors", [])
        
        if warnings:
            lines.append(f"\nWarnings ({len(warnings)}):")
            for warning in warnings:
                lines.append(f"  • {warning}")
                
        if errors:
            lines.append(f"\nErrors ({len(errors)}):")
            for error in errors:
                lines.append(f"  • {error}")
        
        # Cost analysis
        cost_analysis = weights_data.get("cost_analysis", {})
        total_actions = cost_analysis.get("total_actions_analyzed", 0)
        lines.append(f"\nActions analyzed: {total_actions}")
        
        stats = cost_analysis.get("cost_statistics", {})
        if stats:
            lines.append(f"Cost range: {stats.get('min_cost', 0)} - {stats.get('max_cost', 0)}")
            lines.append(f"Average cost: {stats.get('average_cost', 0):.2f}")
        
        # Outliers
        outliers = cost_analysis.get("outliers", [])
        if outliers:
            lines.append(f"\nHigh-cost outliers ({len(outliers)}):")
            for outlier in outliers:
                lines.append(f"  • {outlier.get('name', 'Unknown')}: {outlier.get('cost', 0)} (x{outlier.get('multiplier', 0):.1f})")
        
        # Optimization opportunities
        opportunities = weights_data.get("optimization_opportunities", [])
        if opportunities:
            lines.append(f"\nOptimization opportunities ({len(opportunities)}):")
            for opportunity in opportunities:
                lines.append(f"  • {opportunity}")
        
        # Recommendations
        recommendations = weights_data.get("recommendations", [])
        if recommendations:
            lines.append(f"\nRecommendations ({len(recommendations)}):")
            for rec in recommendations:
                lines.append(f"  • {rec}")
        
        return "\n".join(lines)

    def format_cooldowns_output(self, cooldowns_data: dict[str, Any]) -> str:
        """Format cooldown analysis for CLI display.
        
        Parameters:
            cooldowns_data: Dictionary containing cooldown status and timing analysis
            
        Return values:
            Formatted string representation suitable for CLI output
            
        This method formats cooldown analysis into a readable format for CLI
        display, showing timing status, compliance metrics, and monitoring
        data for debugging action execution timing issues.
        """
        lines = []
        character_name = cooldowns_data.get("character_name", "Unknown")
        lines.append(f"=== COOLDOWN ANALYSIS: {character_name} ===")
        
        # API availability
        api_available = cooldowns_data.get("api_available", False)
        cooldown_manager_available = cooldowns_data.get("cooldown_manager_available", False)
        lines.append(f"API available: {api_available}")
        lines.append(f"Cooldown manager available: {cooldown_manager_available}")
        
        # Cooldown status
        cooldown_status = cooldowns_data.get("cooldown_status", {})
        ready = cooldown_status.get("ready")
        if ready is not None:
            lines.append(f"Character ready: {ready}")
            
        remaining = cooldown_status.get("remaining_seconds")
        if remaining is not None:
            lines.append(f"Remaining time: {remaining:.1f}s")
            
        compliance = cooldown_status.get("compliance_status", "unknown")
        lines.append(f"Compliance status: {compliance}")
        
        reason = cooldown_status.get("reason")
        if reason:
            lines.append(f"Last action: {reason}")
        
        # Timing analysis
        timing_analysis = cooldowns_data.get("timing_analysis", {})
        api_cooldown = timing_analysis.get("api_cooldown_seconds", 30)
        lines.append(f"\nAPI cooldown standard: {api_cooldown}s")
        
        timing_warnings = timing_analysis.get("timing_warnings", [])
        if timing_warnings:
            lines.append(f"\nTiming warnings ({len(timing_warnings)}):")
            for warning in timing_warnings:
                lines.append(f"  • {warning}")
        
        precision_issues = timing_analysis.get("precision_issues", [])
        if precision_issues:
            lines.append(f"\nPrecision issues ({len(precision_issues)}):")
            for issue in precision_issues:
                lines.append(f"  • {issue}")
        
        # Monitoring data
        monitoring_data = cooldowns_data.get("monitoring_data", [])
        if monitoring_data:
            lines.append(f"\nMonitoring data ({len(monitoring_data)} entries):")
            for entry in monitoring_data:
                timestamp = entry.get("timestamp", "Unknown")
                status = entry.get("status", "Unknown")
                lines.append(f"  [{timestamp}] {status}")
                
                cooldown_ready = entry.get("cooldown_ready")
                if cooldown_ready is not None:
                    lines.append(f"    Ready: {cooldown_ready}")
                    
                remaining_secs = entry.get("remaining_seconds")
                if remaining_secs is not None:
                    lines.append(f"    Remaining: {remaining_secs:.1f}s")
        
        # Recommendations
        recommendations = cooldowns_data.get("recommendations", [])
        if recommendations:
            lines.append(f"\nRecommendations ({len(recommendations)}):")
            for rec in recommendations:
                lines.append(f"  • {rec}")
        
        return "\n".join(lines)

    def setup_logging(self, log_level: str) -> None:
        """Configure logging based on CLI arguments.
        
        Parameters:
            log_level: String representing desired logging level (DEBUG, INFO, WARNING, ERROR)
            
        Return values:
            None (configures global logging)
            
        This method configures the application logging system using the async
        logger from src/lib/log.py with the specified level, enabling appropriate
        verbosity for debugging and monitoring AI player operations.
        """
        # Map string level to logging constant
        level_mapping = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR
        }

        level = level_mapping.get(log_level.upper(), logging.INFO)

        # Configure root logger
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Update LogManager's LOG_LEVEL
        log_module.LOG_LEVEL = level

        self.logger.info(f"Logging configured at {log_level} level")


def main() -> None:
    """Main CLI entry point.
    
    Parameters:
        None
        
    Return values:
        None (program entry point)
        
    This function serves as the main entry point for the ArtifactsMMO AI Player
    command-line interface, initializing the CLI manager, parsing arguments,
    and routing commands to appropriate handlers.
    """
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    # Let other exceptions bubble up with full stack traces


async def async_main() -> None:
    """Async wrapper for main CLI functionality.
    
    Parameters:
        None
        
    Return values:
        None (async wrapper)
        
    This function provides an async wrapper for the main CLI functionality,
    enabling proper async/await handling for API calls, AI player operations,
    and other asynchronous components in the system.
    """
    cli_manager = CLIManager()
    parser = cli_manager.create_parser()

    args = parser.parse_args()

    # Setup logging first
    cli_manager.setup_logging(args.log_level)

    # Check if a command was provided
    if not hasattr(args, 'func'):
        parser.print_help()
        return

    # Store token file in args for handlers
    args.token_file = args.token_file

    # Execute the command handler - let exceptions bubble up with full stack traces
    await args.func(args)


if __name__ == "__main__":
    main()

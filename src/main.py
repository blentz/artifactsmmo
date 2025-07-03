#!/usr/bin/env python3
""" main entrypoint """

import asyncio
import logging
import os
import re
import signal
import sys
from pathlib import Path

from artifactsmmo_api_client.client import AuthenticatedClient, Client

from src.cli import get_character_list, parse_args, setup_logging, validate_args
from src.diagnostic_tools import DiagnosticTools
from src.controller.ai_player_controller import AIPlayerController
from src.controller.bulk_data_loader import BulkDataLoader
from src.controller.goal_manager import GOAPGoalManager
from src.controller.goap_execution_manager import GOAPExecutionManager
from src.game.account import Account
from src.game.characters import Characters
from src.game.globals import BASEURL
from src.game.map.state import MapState
from src.lib.actions_data import ActionsData
from src.lib.goap_data import GoapData
from src.lib.httpstatus import extend_http_status
from src.lib.log import safely_start_logger
from src.lib.throttled_transport import ThrottledTransport

MAX_THREADS = 1
RAISE_ON_UNEXPECTED_STATUS = True
DATA_DIR = Path("data")

async def task(character_name=None, args=None):
    """ async task """
    logging.info(f"task started for character: {character_name or 'default'}")
    token = os.environ.get("TOKEN")
    client = None
    
    # Create throttled transport to enforce API rate limits
    throttled_transport = ThrottledTransport()
    
    if token:
        client = AuthenticatedClient(base_url=BASEURL, token=token,
                                     raise_on_unexpected_status=RAISE_ON_UNEXPECTED_STATUS,
                                     httpx_args={'transport': throttled_transport})
        logging.info("🚦 API client created with request throttling (180 req/min)")
    else:
        logging.warning("TOKEN not in ENV. Client NOT authenticated!")
        client = Client(base_url=BASEURL, raise_on_unexpected_status=RAISE_ON_UNEXPECTED_STATUS,
                       httpx_args={'transport': throttled_transport})
        logging.info("🚦 Unauthenticated API client created with request throttling (180 req/min)")
    
    # Initialize goal-driven AI system
    goal_manager = GOAPGoalManager()
    controller = AIPlayerController(client=client, goal_manager=goal_manager)
    logging.info("Goal-driven AI Player Controller created successfully")

    # Set up account and characters with maintenance error handling
    try:
        account = Account(name="wakko666", client=client)
        characters = Characters(account=account, client=client)
        logging.info(f"characters: {characters}")
    except Exception as e:
        error_msg = str(e)
        if "502" in error_msg or "Bad Gateway" in error_msg:
            logging.error("🚨 ArtifactsMMO API is currently under maintenance (502 Bad Gateway)")
            logging.error("🔧 Please check https://api.artifactsmmo.com for service status")
            logging.error("⏰ Try running the application again once maintenance is complete")
            return
        else:
            logging.error(f"Failed to connect to ArtifactsMMO API: {error_msg}")
            raise

    # Use the first available character from the game
    if characters and len(characters) > 0:
        # Get the first character and use its actual data
        game_character = characters[0]
        controller.set_character_state(game_character)
        logging.info(f"Using character: {game_character.name} at position ({game_character.data.get('x', 0)}, {game_character.data.get('y', 0)})")
        
        # Create and set map state for persistence
        map_state = MapState(client=client, name="map")
        map_state.set_learning_callback(controller.learn_from_map_exploration)
        controller.set_map_state(map_state)
        logging.info("Map state initialized for data persistence with learning callbacks")
        
        # Load all game world data using bulk API calls
        bulk_loader = BulkDataLoader()
        bulk_loading_success = bulk_loader.load_all_game_data(client, map_state, controller.knowledge_base)
        if bulk_loading_success:
            logging.info("✅ Bulk game data loading completed - AI has comprehensive world knowledge")
            # Save the loaded data
            map_state.save()
            controller.knowledge_base.save()
        else:
            logging.warning("⚠️ Bulk data loading failed - AI will use discovery-based learning")
    else:
        logging.error("No characters found for the account")
        return
    
    # Record initial character stats
    initial_xp = game_character.data.get('xp', 0)
    initial_level = game_character.data.get('level', 1)
    initial_hp = game_character.data.get('hp', 0)
    
    logging.info(f"Initial character stats - Level: {initial_level}, XP: {initial_xp}, HP: {initial_hp}")
    logging.info("🚀 Starting goal-driven AI mission...")
    
    # GOAP-driven goal execution - let the AI select and pursue goals autonomously
    target_level = 45  # Maximum character level
    
    logging.info(f"🎯 Mission: Autonomous goal-driven progression to MAXIMUM LEVEL {target_level}")
    logging.info("🧠 Strategy: YAML-configured GOAP planning with intelligent goal selection")
    logging.info("🎖️  Ultimate Goal: Reach max character level and all skill max levels!")
    
    # Execute goal-driven mission using GOAP planning
    success = controller.execute_autonomous_mission({'target_level': target_level})
    
    # Report final results
    final_xp = controller.character_state.data.get('xp', 0)
    final_level = controller.character_state.data.get('level', 1)
    final_hp = controller.character_state.data.get('hp', 0)
    
    xp_gained = final_xp - initial_xp
    level_gained = final_level - initial_level
    
    logging.info("🏁 MISSION SUMMARY")
    logging.info(f"📊 XP Progress: {initial_xp} → {final_xp} (+{xp_gained})")
    logging.info(f"📈 Level Progress: {initial_level} → {final_level} (+{level_gained})")
    logging.info(f"❤️  Final HP: {final_hp}")
    
    if success and level_gained > 0:
        logging.info("🎉 MISSION ACCOMPLISHED: Target level achieved!")
    elif success:
        logging.info("✅ MISSION COMPLETED: Goal-driven execution successful!")
    else:
        logging.warning("⚠️  MISSION INCOMPLETE: Goal-driven execution did not reach target")
        
    if xp_gained > 0:
        logging.info("⚡ AI successfully gained XP through autonomous goal-driven planning!")
    else:
        logging.warning("❌ No XP gained - review goal selection and action execution")
    
    logging.info("task finished")


def clean_data_files():
    """Clear all generated data files."""
    data_files = ["world.yaml", "map.yaml", "knowledge.yaml"]
    for filename in data_files:
        file_path = DATA_DIR / filename
        if file_path.exists():
            logging.info(f"Deleting {file_path}")
            file_path.unlink()
    logging.info("All generated data files cleared")


def show_goal_plan(goal_string, client, args):
    """Show the GOAP plan for achieving a specified goal."""
    # Use new diagnostic tools
    offline = not args.live if hasattr(args, 'live') else True
    clean_state = args.clean_state if hasattr(args, 'clean_state') else False
    custom_state = args.state if hasattr(args, 'state') else None
    
    tools = DiagnosticTools(
        client=client,
        offline=offline,
        clean_state=clean_state,
        custom_state=custom_state
    )
    
    tools.show_goal_plan(goal_string)


def evaluate_user_plan(plan_string, client, args):
    """Evaluate a user-defined plan."""
    # Use new diagnostic tools
    offline = not args.live if hasattr(args, 'live') else True
    clean_state = args.clean_state if hasattr(args, 'clean_state') else False
    custom_state = args.state if hasattr(args, 'state') else None
    
    tools = DiagnosticTools(
        client=client,
        offline=offline,
        clean_state=clean_state,
        custom_state=custom_state
    )
    
    tools.evaluate_user_plan(plan_string)


def create_character(character_name, client):
    """Create a new character."""
    logging.info(f"Creating character: {character_name}")
    # TODO: Implement character creation via API
    logging.info("Character creation not yet implemented")


def delete_character(character_name, client):
    """Delete an existing character."""
    logging.info(f"Deleting character: {character_name}")
    # TODO: Implement character deletion via API
    logging.info("Character deletion not yet implemented")


def handle_shutdown(signum, frame):
    """Handle graceful shutdown."""
    logging.info("Shutdown signal received, cleaning up...")
    sys.exit(0)

async def main():
    """ main coroutine """
    # Parse command-line arguments
    args = parse_args()
    
    # Set up logging based on CLI argument
    setup_logging(args.log_level)
    
    # Validate arguments
    if not validate_args(args):
        sys.exit(1)
    
    # Start async logger
    await safely_start_logger()
    logging.info("Execution starting.")

    extend_http_status() # patch ArtifactsMMO custom codes into http.HTTPStatus
    
    # Handle daemon mode
    if args.daemon:
        logging.info("Starting in daemon mode...")
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)
    
    # Create client for special operations
    if args.clean or args.create_character or args.delete_character or args.goal_planner or args.evaluate_plan:
        token = os.environ.get("TOKEN")
        throttled_transport = ThrottledTransport()
        
        if token:
            client = AuthenticatedClient(base_url=BASEURL, token=token,
                                         raise_on_unexpected_status=RAISE_ON_UNEXPECTED_STATUS,
                                         httpx_args={'transport': throttled_transport})
        else:
            logging.warning("TOKEN not in ENV. Client NOT authenticated!")
            client = Client(base_url=BASEURL, raise_on_unexpected_status=RAISE_ON_UNEXPECTED_STATUS,
                           httpx_args={'transport': throttled_transport})
        
        # Handle special operations
        if args.clean:
            clean_data_files()
            return
        
        if args.create_character:
            create_character(args.create_character, client)
            return
        
        if args.delete_character:
            delete_character(args.delete_character, client)
            return
        
        if args.goal_planner:
            show_goal_plan(args.goal_planner, client, args)
            return
        
        if args.evaluate_plan:
            evaluate_user_plan(args.evaluate_plan, client, args)
            return
    
    # Normal execution - run character(s)
    character_list = get_character_list(args)
    
    if character_list:
        # Run multiple characters in parallel
        logging.info(f"Running {len(character_list)} characters in parallel: {character_list}")
        async with asyncio.TaskGroup() as group:
            for char_name in character_list:
                _ = group.create_task(task(character_name=char_name, args=args))
    else:
        # Run single character (default behavior)
        async with asyncio.TaskGroup() as group:
            for _ in range(MAX_THREADS):
                _ = group.create_task(task(args=args))

    logging.info("Execution complete.")

if "__main__" in __name__:
    asyncio.run(main())

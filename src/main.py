#!/usr/bin/env python3
""" main entrypoint """

import asyncio
import logging
import os
import sys
import signal
from pathlib import Path

from artifactsmmo_api_client.client import AuthenticatedClient, Client

from src.game.globals import BASEURL
from src.lib.httpstatus import extend_http_status
from src.lib.log import safely_start_logger
from src.lib.throttled_transport import ThrottledTransport, ThrottledAsyncTransport
from src.controller.ai_player_controller import AIPlayerController
from src.controller.goal_manager import GOAPGoalManager
from src.game.account import Account
from src.game.characters import Characters
from src.game.character.state import CharacterState
from src.game.map.state import MapState
from src.cli import parse_args, validate_args, setup_logging, get_character_list

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
        from src.controller.bulk_data_loader import BulkDataLoader
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


def show_goal_plan(goal_string, client):
    """Show the GOAP plan for achieving a specified goal."""
    from src.lib.actions_data import ActionsData
    from src.lib.goap_data import GoapData
    from src.controller.goap_execution_manager import GOAPExecutionManager
    from src.controller.goal_manager import GOAPGoalManager
    
    logging.info(f"\n=== GOAP Plan Analysis for Goal: {goal_string} ===")
    
    # Initialize managers
    goap_executor = GOAPExecutionManager()
    actions_data = ActionsData("config/actions.yaml")
    goap_data = GoapData("data/world.yaml")
    
    # Initialize goal manager to access goal templates
    goal_manager = GOAPGoalManager()
    
    # Load actions configuration
    actions_config = actions_data.get_actions()
    logging.info(f"Loaded {len(actions_config)} available actions")
    
    # Parse goal string into goal state using goal templates when available
    goal_state = {}
    if goal_string in goal_manager.goal_templates:
        # Use the target_state from the goal template
        goal_template = goal_manager.goal_templates[goal_string]
        goal_state = goal_template.get('target_state', {}).copy()
        logging.info(f"Using goal template '{goal_string}' with target state: {goal_state}")
    elif "level" in goal_string:
        # Extract level number from goal string
        import re
        level_match = re.search(r'level[\s_]*(\d+)', goal_string, re.IGNORECASE)
        if level_match:
            target_level = int(level_match.group(1))
            goal_state['character_level_ge'] = target_level
            logging.info(f"Goal: Reach level {target_level}")
    elif "xp" in goal_string:
        # XP-related goal
        goal_state['has_xp'] = True
        logging.info("Goal: Gain XP")
    elif "skill" in goal_string:
        # Skill-related goal
        for skill in ['combat', 'woodcutting', 'mining', 'fishing', 'weaponcrafting', 
                     'gearcrafting', 'jewelrycrafting', 'cooking', 'alchemy']:
            if skill in goal_string.lower():
                goal_state[f'{skill}_skill_ge'] = 10  # Default target
                logging.info(f"Goal: Advance {skill} skill")
                break
    else:
        # Try to parse as a direct state variable
        if '=' in goal_string:
            key, value = goal_string.split('=', 1)
            goal_state[key.strip()] = value.strip() == 'true' if value.strip() in ['true', 'false'] else value.strip()
        else:
            goal_state[goal_string] = True
        logging.info(f"Goal state: {goal_state}")
    
    # Load current world state (without hardcoded overrides)
    # Let the GOAP execution manager handle start state configuration
    current_state = goap_data.data.copy()
    
    logging.info(f"\nCurrent world state has {len(current_state)} variables")
    
    # Create plan
    logging.info("\nGenerating GOAP plan...")
    plan = goap_executor.create_plan(current_state, goal_state, actions_config)
    
    if plan:
        logging.info(f"\n✅ Plan found with {len(plan)} actions:\n")
        total_weight = 0
        for i, action in enumerate(plan, 1):
            action_name = action.get('name', 'unknown')
            action_cfg = actions_config.get(action_name, {})
            weight = action_cfg.get('weight', 1.0)
            total_weight += weight
            
            logging.info(f"{i}. {action_name} (weight: {weight})")
            
            # Show conditions
            conditions = action_cfg.get('conditions', {})
            if conditions:
                logging.info("   Requires:")
                for key, value in conditions.items():
                    logging.info(f"     - {key}: {value}")
            
            # Show effects
            reactions = action_cfg.get('reactions', {})
            if reactions:
                logging.info("   Effects:")
                for key, value in reactions.items():
                    logging.info(f"     - {key}: {value}")
            
            logging.info("")
        
        logging.info(f"Total plan cost: {total_weight:.2f}")
    else:
        logging.info("\n❌ No plan found!")
        logging.info("\nPossible reasons:")
        logging.info("- Goal is already satisfied in current state")
        logging.info("- No action sequence can achieve the goal")
        logging.info("- Missing prerequisite states")
        
        # Show current state values relevant to goal
        logging.info("\nRelevant current state:")
        for key in goal_state:
            if key in current_state:
                logging.info(f"  {key}: {current_state[key]}")
            else:
                logging.info(f"  {key}: <not set>")


def evaluate_user_plan(plan_string, client):
    """Evaluate a user-defined plan."""
    from src.lib.actions_data import ActionsData
    from src.lib.goap_data import GoapData
    
    logging.info(f"\n=== Evaluating User Plan: {plan_string} ===")
    
    # Parse plan string (e.g., "move->fight->rest" or "move,fight,rest")
    separators = ['->', ',', '|', ';']
    plan_actions = None
    for sep in separators:
        if sep in plan_string:
            plan_actions = [a.strip() for a in plan_string.split(sep)]
            break
    if not plan_actions:
        plan_actions = [plan_string.strip()]
    
    logging.info(f"\nPlan contains {len(plan_actions)} actions: {plan_actions}")
    
    # Load actions configuration
    actions_data = ActionsData("config/actions.yaml")
    actions_config = actions_data.get_actions()
    goap_data = GoapData("data/world.yaml")
    
    # Start with current world state
    current_state = goap_data.data.copy()
    # Add defaults
    if 'character_alive' not in current_state:
        current_state['character_alive'] = True
    
    logging.info(f"\nStarting state has {len(current_state)} variables")
    
    # Evaluate each action in sequence
    plan_valid = True
    total_cost = 0
    
    for i, action_name in enumerate(plan_actions, 1):
        logging.info(f"\n{i}. Evaluating action: {action_name}")
        
        if action_name not in actions_config:
            logging.error(f"   ❌ ERROR: Unknown action '{action_name}'")
            logging.info("   Available actions: " + ", ".join(sorted(actions_config.keys())))
            plan_valid = False
            break
        
        action_cfg = actions_config[action_name]
        conditions = action_cfg.get('conditions', {})
        reactions = action_cfg.get('reactions', {})
        weight = action_cfg.get('weight', 1.0)
        total_cost += weight
        
        # Check if conditions are met
        conditions_met = True
        logging.info("   Checking conditions:")
        for key, required_value in conditions.items():
            current_value = current_state.get(key, False)
            
            # Handle comparison operators in key names
            if key.endswith('_ge'):
                # Greater than or equal comparison
                base_key = key[:-3]
                current_val = current_state.get(base_key, 0)
                met = current_val >= required_value
                logging.info(f"     - {base_key} >= {required_value}: {current_val} {'✓' if met else '✗'}")
                if not met:
                    conditions_met = False
            elif key.endswith('_lt'):
                # Less than comparison
                base_key = key[:-3]
                current_val = current_state.get(base_key, float('inf'))
                met = current_val < required_value
                logging.info(f"     - {base_key} < {required_value}: {current_val} {'✓' if met else '✗'}")
                if not met:
                    conditions_met = False
            else:
                # Direct equality check
                met = current_value == required_value
                logging.info(f"     - {key} = {required_value}: {current_value} {'✓' if met else '✗'}")
                if not met:
                    conditions_met = False
        
        if not conditions_met:
            logging.error(f"   ❌ Cannot execute {action_name}: conditions not met")
            plan_valid = False
            break
        
        # Apply reactions to state
        logging.info("   Applying effects:")
        for key, value in reactions.items():
            old_value = current_state.get(key, None)
            current_state[key] = value
            logging.info(f"     - {key}: {old_value} → {value}")
        
        logging.info(f"   ✓ Action executable (cost: {weight})")
    
    # Summary
    logging.info(f"\n=== Plan Evaluation Summary ===")
    if plan_valid:
        logging.info(f"✅ Plan is VALID and executable")
        logging.info(f"Total cost: {total_cost}")
        logging.info(f"\nFinal state changes:")
        
        # Compare initial vs final state
        initial_state = goap_data.data.copy()
        for key in set(initial_state.keys()) | set(current_state.keys()):
            initial_val = initial_state.get(key, None)
            final_val = current_state.get(key, None)
            if initial_val != final_val:
                logging.info(f"  {key}: {initial_val} → {final_val}")
    else:
        logging.info(f"❌ Plan is INVALID and cannot be executed")
        logging.info("Fix the issues above before the plan can work")
    
    # Suggest improvements
    if plan_valid:
        logging.info("\nPlan optimization suggestions:")
        # Check for redundant actions
        if len(plan_actions) != len(set(plan_actions)):
            logging.info("- Plan contains duplicate actions")
        # Check for high-cost actions
        for action in plan_actions:
            if actions_config.get(action, {}).get('weight', 1.0) > 5:
                logging.info(f"- Action '{action}' has high cost, consider alternatives")


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
            show_goal_plan(args.goal_planner, client)
            return
        
        if args.evaluate_plan:
            evaluate_user_plan(args.evaluate_plan, client)
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

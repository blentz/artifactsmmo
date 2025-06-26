#!/usr/bin/env python3
""" main entrypoint """

import asyncio
import logging
import os

from artifactsmmo_api_client.client import AuthenticatedClient, Client

from src.game.globals import BASEURL
from src.lib.httpstatus import extend_http_status
from src.lib.log import safely_start_logger
from src.controller.ai_player_controller import AIPlayerController
from src.controller.goal_manager import GOAPGoalManager
from src.game.account import Account
from src.game.characters import Characters
from src.game.character.state import CharacterState
from src.game.map.state import MapState

MAX_THREADS = 1
RAISE_ON_UNEXPECTED_STATUS = True

async def task():
    """ async task """
    logging.info("task started")
    token = os.environ.get("TOKEN")
    client = None
    if token:
        client = AuthenticatedClient(base_url=BASEURL, token=token,
                                     raise_on_unexpected_status=RAISE_ON_UNEXPECTED_STATUS)
    else:
        logging.warning("TOKEN not in ENV. Client NOT authenticated!")
        client = Client(base_url=BASEURL, raise_on_unexpected_status=RAISE_ON_UNEXPECTED_STATUS)
    
    # Initialize goal-driven AI system
    goal_manager = GOAPGoalManager()
    controller = AIPlayerController(client=client, goal_manager=goal_manager)
    logging.info("Goal-driven AI Player Controller created successfully")

    # Set up account and characters
    account = Account(name="wakko666", client=client)
    characters = Characters(account=account, client=client)
    logging.info(f"characters: {characters}")

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
    target_level = 2
    
    logging.info(f"🎯 Mission: Autonomous goal-driven progression to level {target_level}")
    logging.info("🧠 Strategy: YAML-configured GOAP planning with intelligent goal selection")
    
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

async def main():
    """ main coroutine """
    await safely_start_logger()
    logging.info("Execution starting.")

    extend_http_status() # patch ArtifactsMMO custom codes into http.HTTPStatus

    async with asyncio.TaskGroup() as group:
        for _ in range(MAX_THREADS):
            _ = group.create_task(task())

    logging.info("Execution complete.")

if "__main__" in __name__:
    asyncio.run(main())

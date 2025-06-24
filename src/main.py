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
from src.game.account import Account
from src.game.characters import Characters
from src.game.character.state import CharacterState

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
    # Initialize AI Player Controller
    controller = AIPlayerController(client=client)
    logging.info("AI Player Controller created successfully")

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
    else:
        logging.error("No characters found for the account")
        return
    
    # Record initial character stats
    initial_xp = game_character.data.get('xp', 0)
    initial_level = game_character.data.get('level', 1)
    initial_hp = game_character.data.get('hp', 0)
    
    logging.info(f"Initial character stats - Level: {initial_level}, XP: {initial_xp}, HP: {initial_hp}")
    logging.info("🚀 Starting AI LEVEL UP GOAL mission...")
    
    # Define the goal: use the comprehensive level_up goal
    target_level = 2
    actions_config_file = "data/actions.yaml"
    
    logging.info(f"🎯 Mission: Execute level_up goal to reach level {target_level}")
    logging.info("🧠 Strategy: GOAP-based monster hunting with intelligent rest management")
    
    # Use the new level_up_goal method for comprehensive hunting strategy
    success = controller.level_up_goal(target_level, actions_config_file)
    
    # Additional summary (level_up_goal already provides detailed reporting)
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
        logging.info("🎉 MISSION ACCOMPLISHED: Level up goal achieved!")
    elif success:
        logging.info("✅ MISSION COMPLETED: Goal state reached!")
    else:
        logging.warning("⚠️  MISSION INCOMPLETE: Could not achieve level up goal")
        
    if xp_gained > 0:
        logging.info("⚡ AI successfully gained XP through intelligent monster hunting!")
    else:
        logging.warning("❌ No XP gained - character may need manual intervention")
    
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

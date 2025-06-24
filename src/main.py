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
    logging.info("Starting slime hunting mission...")
    
    # Find and move to the nearest slime
    success = controller.find_and_move_to_nearest_slime(search_radius=10)
    
    if success:
        logging.info("Successfully found and moved to slime location!")
        
        # Now attack the slime until it's dead
        logging.info("Beginning slime combat...")
        from src.controller.actions.attack import AttackAction
        
        attack_action = AttackAction(char_name=game_character.name)
        max_attacks = 20  # Safety limit to prevent infinite loop
        attacks_made = 0
        
        while attacks_made < max_attacks:
            attacks_made += 1
            logging.info(f"Attack attempt {attacks_made}...")
            
            try:
                # Pass character state for HP safety checking
                attack_response = attack_action.execute(client, character_state=controller.character_state)
                
                if attack_response and hasattr(attack_response, 'data'):
                    attack_data = attack_response.data
                    
                    # Log the full response for debugging
                    logging.info(f"Full attack response: {attack_response}")
                    
                    # Update character state with new stats
                    if hasattr(attack_data, 'character'):
                        char_data = attack_data.character
                        controller.character_state.data['level'] = char_data.level
                        controller.character_state.data['xp'] = char_data.xp
                        controller.character_state.data['hp'] = char_data.hp
                        controller.character_state.data['x'] = char_data.x
                        controller.character_state.data['y'] = char_data.y
                        controller.character_state.save()
                        
                        logging.info(f"After attack {attacks_made}: Level {char_data.level}, XP {char_data.xp}, HP {char_data.hp}")
                    
                    # Check if the monster was defeated
                    if hasattr(attack_data, 'monster'):
                        monster_data = attack_data.monster
                        if hasattr(monster_data, 'hp'):
                            logging.info(f"Monster HP: {monster_data.hp}")
                            if monster_data.hp <= 0:
                                logging.info("🎉 Slime defeated!")
                                break
                        else:
                            logging.info(f"Monster data: {monster_data}")
                    
                    # Check for fight result and details
                    if hasattr(attack_data, 'fight'):
                        fight_data = attack_data.fight
                        logging.info(f"Fight data: {fight_data}")
                        
                        if hasattr(fight_data, 'result'):
                            logging.info(f"Fight result: {fight_data.result}")
                            if fight_data.result == 'win':
                                logging.info("🎉 Victory! Slime has been defeated!")
                                break
                        
                        if hasattr(fight_data, 'xp') and fight_data.xp > 0:
                            logging.info(f"XP gained this fight: {fight_data.xp}")
                    
                    # Check for any other fields that might contain XP or victory information
                    logging.info(f"Attack data attributes: {dir(attack_data)}")
                
                else:
                    logging.warning(f"Attack {attacks_made} failed - no response data")
                    break
                    
            except Exception as e:
                error_msg = str(e)
                logging.error(f"Error during attack {attacks_made}: {error_msg}")
                
                # Check if it's a cooldown error
                if "cooldown" in error_msg.lower():
                    import re
                    import time
                    
                    # Extract cooldown time from error message
                    cooldown_match = re.search(r'(\d+\.?\d*)\s*seconds', error_msg)
                    if cooldown_match:
                        cooldown_time = float(cooldown_match.group(1))
                        logging.info(f"Character in cooldown. Waiting {cooldown_time + 1} seconds...")
                        time.sleep(cooldown_time + 1)  # Add 1 second buffer
                        attacks_made -= 1  # Don't count this as a failed attack
                        continue
                break
        
        # Report final results
        final_xp = controller.character_state.data.get('xp', 0)
        final_level = controller.character_state.data.get('level', 1)
        final_hp = controller.character_state.data.get('hp', 0)
        
        xp_gained = final_xp - initial_xp
        level_gained = final_level - initial_level
        
        logging.info("=== SLIME HUNTING MISSION COMPLETE ===")
        logging.info(f"Initial stats - Level: {initial_level}, XP: {initial_xp}, HP: {initial_hp}")
        logging.info(f"Final stats   - Level: {final_level}, XP: {final_xp}, HP: {final_hp}")
        logging.info(f"Gains: +{xp_gained} XP, +{level_gained} levels")
        logging.info(f"Total attacks made: {attacks_made}")
        
        if xp_gained > 0:
            logging.info("✅ SUCCESS: Character gained XP, confirming slime was killed!")
        else:
            logging.warning("❌ WARNING: No XP gained - slime may not have been defeated")
            
    else:
        logging.info("No slimes found within search radius or movement failed")
    
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

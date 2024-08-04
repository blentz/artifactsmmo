#!/usr/bin/env python3

from artifacts_openapi import APIConfig
from artifacts_openapi.services.async_Mycharacters_service import get_my_characters_my_characters_get
from artifacts_openapi.services.Mycharacters_service import action_fight_my__name__action_fight_post
from artifacts_openapi.models.MyCharactersListSchema import MyCharactersListSchema
from artifacts_openapi.models.CharacterFightResponseSchema import CharacterFightResponseSchema

from lib.map.map import scan_map_for, move_char_to

import asyncio

ARTIFACTS_BASE_URL: str = "https://api.artifactsmmo.com"

if '__main__' in __name__:
    apiconfig = APIConfig(base_path=ARTIFACTS_BASE_URL)

    # select characters
    my_characters: MyCharactersListSchema = asyncio.run(get_my_characters_my_characters_get(api_config_override=apiconfig)).data
    for char in my_characters:
        location: tuple = (char.x, char.y)
        print("{}: {}".format(char.name, location))

        # find chicken, move to it
        result: tuple = scan_map_for(item="chicken", origin=location, api_config_override=apiconfig)
        if result:
            print("Chicken found at {}".format(result))
            if result != location:
                moved: bool = move_char_to(name=char.name, x=result[0], y=result[1], api_config_override=apiconfig)
                if moved:
                    print("{} moved to {}".format(char, result))
        
        # fight chicken
        result: CharacterFightResponseSchema = action_fight_my__name__action_fight_post(name=char.name, api_config_override=apiconfig).data
        print(result.fight)
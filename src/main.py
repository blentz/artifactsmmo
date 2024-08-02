#!/usr/bin/env python3

from artifacts_openapi import APIConfig
from artifacts_openapi.services.async_Characters_service import get_character_characters__name__get

import asyncio

ARTIFACTS_BASE_URL: str = "https://api.artifactsmmo.com"

if '__main__' in __name__:
    apiconfig = APIConfig(base_path=ARTIFACTS_BASE_URL)

    char = asyncio.run(get_character_characters__name__get(name="wakko", api_config_override=apiconfig))
    print(char)
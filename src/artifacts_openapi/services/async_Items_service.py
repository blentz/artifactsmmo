import json
from typing import *

import httpx

from ..api_config import APIConfig, HTTPException
from ..models import *


async def get_all_items_items__get(
    min_level: Optional[int] = None,
    max_level: Optional[int] = None,
    name: Optional[str] = None,
    type: Optional[str] = None,
    craft_skill: Optional[str] = None,
    craft_material: Optional[str] = None,
    page: Optional[int] = None,
    size: Optional[int] = None,
    api_config_override: Optional[APIConfig] = None,
) -> DataPage_ItemSchema_:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/items/"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer { api_config.get_access_token() }",
    }
    query_params: Dict[str, Any] = {
        "min_level": min_level,
        "max_level": max_level,
        "name": name,
        "type": type,
        "craft_skill": craft_skill,
        "craft_material": craft_material,
        "page": page,
        "size": size,
    }

    query_params = {
        key: value for (key, value) in query_params.items() if value is not None
    }

    async with httpx.AsyncClient(
        base_url=base_path, verify=api_config.verify
    ) as client:
        response = await client.request(
            "get",
            httpx.URL(path),
            headers=headers,
            params=query_params,
        )

    if response.status_code != 200:
        raise HTTPException(
            response.status_code, f" failed with status code: {response.status_code}"
        )

    return (
        DataPage_ItemSchema_(**response.json())
        if response.json() is not None
        else DataPage_ItemSchema_()
    )


async def get_item_items__code__get(
    code: str, api_config_override: Optional[APIConfig] = None
) -> ItemResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/items/{code}"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer { api_config.get_access_token() }",
    }
    query_params: Dict[str, Any] = {}

    query_params = {
        key: value for (key, value) in query_params.items() if value is not None
    }

    async with httpx.AsyncClient(
        base_url=base_path, verify=api_config.verify
    ) as client:
        response = await client.request(
            "get",
            httpx.URL(path),
            headers=headers,
            params=query_params,
        )

    if response.status_code != 200:
        raise HTTPException(
            response.status_code, f" failed with status code: {response.status_code}"
        )

    return (
        ItemResponseSchema(**response.json())
        if response.json() is not None
        else ItemResponseSchema()
    )

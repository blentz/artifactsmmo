import json
from typing import *

import httpx

from ..api_config import APIConfig, HTTPException
from ..models import *


async def get_all_resources_resources__get(
    min_level: Optional[int] = None,
    max_level: Optional[int] = None,
    skill: Optional[str] = None,
    drop: Optional[str] = None,
    page: Optional[int] = None,
    size: Optional[int] = None,
    api_config_override: Optional[APIConfig] = None,
) -> DataPage_ResourceSchema_:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/resources/"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer { api_config.get_access_token() }",
    }
    query_params: Dict[str, Any] = {
        "min_level": min_level,
        "max_level": max_level,
        "skill": skill,
        "drop": drop,
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
        DataPage_ResourceSchema_(**response.json())
        if response.json() is not None
        else DataPage_ResourceSchema_()
    )


async def get_resource_resources__code__get(
    code: str, api_config_override: Optional[APIConfig] = None
) -> ResourceResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/resources/{code}"
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
        ResourceResponseSchema(**response.json())
        if response.json() is not None
        else ResourceResponseSchema()
    )

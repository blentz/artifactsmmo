import json
from typing import *

import httpx

from ..api_config import APIConfig, HTTPException
from ..models import *


async def get_all_events_events__get(
    page: Optional[int] = None,
    size: Optional[int] = None,
    api_config_override: Optional[APIConfig] = None,
) -> DataPage_ActiveEventSchema_:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/events/"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer { api_config.get_access_token() }",
    }
    query_params: Dict[str, Any] = {"page": page, "size": size}

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
        DataPage_ActiveEventSchema_(**response.json())
        if response.json() is not None
        else DataPage_ActiveEventSchema_()
    )

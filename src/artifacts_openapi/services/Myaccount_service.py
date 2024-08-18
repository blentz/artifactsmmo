import json
from typing import *

import httpx

from ..api_config import APIConfig, HTTPException
from ..models import *


def get_bank_items_my_bank_items_get(
    item_code: Optional[str] = None,
    page: Optional[int] = None,
    size: Optional[int] = None,
    api_config_override: Optional[APIConfig] = None,
) -> DataPage_SimpleItemSchema_:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/bank/items"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer { api_config.get_access_token() }",
    }
    query_params: Dict[str, Any] = {"item_code": item_code, "page": page, "size": size}

    query_params = {
        key: value for (key, value) in query_params.items() if value is not None
    }

    with httpx.Client(base_url=base_path, verify=api_config.verify) as client:
        response = client.request(
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
        DataPage_SimpleItemSchema_(**response.json())
        if response.json() is not None
        else DataPage_SimpleItemSchema_()
    )


def get_bank_golds_my_bank_gold_get(
    api_config_override: Optional[APIConfig] = None,
) -> GoldBankResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/bank/gold"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer { api_config.get_access_token() }",
    }
    query_params: Dict[str, Any] = {}

    query_params = {
        key: value for (key, value) in query_params.items() if value is not None
    }

    with httpx.Client(base_url=base_path, verify=api_config.verify) as client:
        response = client.request(
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
        GoldBankResponseSchema(**response.json())
        if response.json() is not None
        else GoldBankResponseSchema()
    )


def change_password_my_change_password_post(
    data: ChangePassword, api_config_override: Optional[APIConfig] = None
) -> ResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/change_password"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer { api_config.get_access_token() }",
    }
    query_params: Dict[str, Any] = {}

    query_params = {
        key: value for (key, value) in query_params.items() if value is not None
    }

    with httpx.Client(base_url=base_path, verify=api_config.verify) as client:
        response = client.request(
            "post",
            httpx.URL(path),
            headers=headers,
            params=query_params,
            json=data.dict(),
        )

    if response.status_code != 200:
        raise HTTPException(
            response.status_code, f" failed with status code: {response.status_code}"
        )

    return (
        ResponseSchema(**response.json())
        if response.json() is not None
        else ResponseSchema()
    )

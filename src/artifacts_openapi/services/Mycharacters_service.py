import json
from typing import *

import httpx

from ..api_config import APIConfig, HTTPException
from ..models import *


def action_move_my__name__action_move_post(
    name: str, data: DestinationSchema, api_config_override: Optional[APIConfig] = None
) -> CharacterMovementResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/{name}/action/move"
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
        CharacterMovementResponseSchema(**response.json())
        if response.json() is not None
        else CharacterMovementResponseSchema()
    )


def action_equip_item_my__name__action_equip_post(
    name: str, data: EquipSchema, api_config_override: Optional[APIConfig] = None
) -> EquipmentResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/{name}/action/equip"
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
        EquipmentResponseSchema(**response.json())
        if response.json() is not None
        else EquipmentResponseSchema()
    )


def action_unequip_item_my__name__action_unequip_post(
    name: str, data: UnequipSchema, api_config_override: Optional[APIConfig] = None
) -> EquipmentResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/{name}/action/unequip"
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
        EquipmentResponseSchema(**response.json())
        if response.json() is not None
        else EquipmentResponseSchema()
    )


def action_fight_my__name__action_fight_post(
    name: str, api_config_override: Optional[APIConfig] = None
) -> CharacterFightResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/{name}/action/fight"
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
        )

    if response.status_code != 200:
        raise HTTPException(
            response.status_code, f" failed with status code: {response.status_code}"
        )

    return (
        CharacterFightResponseSchema(**response.json())
        if response.json() is not None
        else CharacterFightResponseSchema()
    )


def action_gathering_my__name__action_gathering_post(
    name: str, api_config_override: Optional[APIConfig] = None
) -> SkillResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/{name}/action/gathering"
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
        )

    if response.status_code != 200:
        raise HTTPException(
            response.status_code, f" failed with status code: {response.status_code}"
        )

    return (
        SkillResponseSchema(**response.json())
        if response.json() is not None
        else SkillResponseSchema()
    )


def action_crafting_my__name__action_crafting_post(
    name: str, data: CraftingSchema, api_config_override: Optional[APIConfig] = None
) -> SkillResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/{name}/action/crafting"
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
        SkillResponseSchema(**response.json())
        if response.json() is not None
        else SkillResponseSchema()
    )


def action_deposit_bank_my__name__action_bank_deposit_post(
    name: str, data: SimpleItemSchema, api_config_override: Optional[APIConfig] = None
) -> ActionItemBankResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/{name}/action/bank/deposit"
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
        ActionItemBankResponseSchema(**response.json())
        if response.json() is not None
        else ActionItemBankResponseSchema()
    )


def action_deposit_bank_gold_my__name__action_bank_deposit_gold_post(
    name: str,
    data: DepositWithdrawGoldSchema,
    api_config_override: Optional[APIConfig] = None,
) -> GoldResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/{name}/action/bank/deposit/gold"
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
        GoldResponseSchema(**response.json())
        if response.json() is not None
        else GoldResponseSchema()
    )


def action_recycling_my__name__action_recycling_post(
    name: str, data: RecyclingSchema, api_config_override: Optional[APIConfig] = None
) -> RecyclingResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/{name}/action/recycling"
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
        RecyclingResponseSchema(**response.json())
        if response.json() is not None
        else RecyclingResponseSchema()
    )


def action_withdraw_bank_my__name__action_bank_withdraw_post(
    name: str, data: SimpleItemSchema, api_config_override: Optional[APIConfig] = None
) -> ActionItemBankResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/{name}/action/bank/withdraw"
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
        ActionItemBankResponseSchema(**response.json())
        if response.json() is not None
        else ActionItemBankResponseSchema()
    )


def action_withdraw_bank_gold_my__name__action_bank_withdraw_gold_post(
    name: str,
    data: DepositWithdrawGoldSchema,
    api_config_override: Optional[APIConfig] = None,
) -> GoldResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/{name}/action/bank/withdraw/gold"
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
        GoldResponseSchema(**response.json())
        if response.json() is not None
        else GoldResponseSchema()
    )


def action_ge_buy_item_my__name__action_ge_buy_post(
    name: str,
    data: GETransactionItemSchema,
    api_config_override: Optional[APIConfig] = None,
) -> GETransactionResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/{name}/action/ge/buy"
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
        GETransactionResponseSchema(**response.json())
        if response.json() is not None
        else GETransactionResponseSchema()
    )


def action_ge_sell_item_my__name__action_ge_sell_post(
    name: str,
    data: GETransactionItemSchema,
    api_config_override: Optional[APIConfig] = None,
) -> GETransactionResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/{name}/action/ge/sell"
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
        GETransactionResponseSchema(**response.json())
        if response.json() is not None
        else GETransactionResponseSchema()
    )


def action_accept_new_task_my__name__action_task_new_post(
    name: str, api_config_override: Optional[APIConfig] = None
) -> TaskResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/{name}/action/task/new"
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
        )

    if response.status_code != 200:
        raise HTTPException(
            response.status_code, f" failed with status code: {response.status_code}"
        )

    return (
        TaskResponseSchema(**response.json())
        if response.json() is not None
        else TaskResponseSchema()
    )


def action_complete_task_my__name__action_task_complete_post(
    name: str, api_config_override: Optional[APIConfig] = None
) -> TaskRewardResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/{name}/action/task/complete"
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
        )

    if response.status_code != 200:
        raise HTTPException(
            response.status_code, f" failed with status code: {response.status_code}"
        )

    return (
        TaskRewardResponseSchema(**response.json())
        if response.json() is not None
        else TaskRewardResponseSchema()
    )


def action_task_exchange_my__name__action_task_exchange_post(
    name: str, api_config_override: Optional[APIConfig] = None
) -> TaskRewardResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/{name}/action/task/exchange"
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
        )

    if response.status_code != 200:
        raise HTTPException(
            response.status_code, f" failed with status code: {response.status_code}"
        )

    return (
        TaskRewardResponseSchema(**response.json())
        if response.json() is not None
        else TaskRewardResponseSchema()
    )


def action_delete_item_my__name__action_delete_post(
    name: str, data: SimpleItemSchema, api_config_override: Optional[APIConfig] = None
) -> DeleteItemResponseSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/{name}/action/delete"
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
        DeleteItemResponseSchema(**response.json())
        if response.json() is not None
        else DeleteItemResponseSchema()
    )


def get_all_characters_logs_my_logs_get(
    page: Optional[int] = None,
    size: Optional[int] = None,
    api_config_override: Optional[APIConfig] = None,
) -> DataPage_LogSchema_:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/logs"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer { api_config.get_access_token() }",
    }
    query_params: Dict[str, Any] = {"page": page, "size": size}

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
        DataPage_LogSchema_(**response.json())
        if response.json() is not None
        else DataPage_LogSchema_()
    )


def get_my_characters_my_characters_get(
    api_config_override: Optional[APIConfig] = None,
) -> MyCharactersListSchema:
    api_config = api_config_override if api_config_override else APIConfig()

    base_path = api_config.base_path
    path = f"/my/characters"
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
        MyCharactersListSchema(**response.json())
        if response.json() is not None
        else MyCharactersListSchema()
    )

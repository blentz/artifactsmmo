from artifacts_openapi import APIConfig
from artifacts_openapi.services.Mycharacters_service import (
    get_my_characters_my_characters_get,
    action_fight_my__name__action_fight_post,
    action_move_my__name__action_move_post,
)
from artifacts_openapi.models.MyCharactersListSchema import MyCharactersListSchema
from artifacts_openapi.models.CharacterFightResponseSchema import (
    CharacterFightResponseSchema,
)
from artifacts_openapi.models.CharacterMovementResponseSchema import (
    CharacterMovementResponseSchema,
)
from artifacts_openapi.models.DestinationSchema import DestinationSchema

from .yaml_data import YamlData


class CharacterState(YamlData):
    """Character model."""

    _api_config: APIConfig = None
    name: str = None

    def __init__(self, name: str, api_config_override: APIConfig = None):
        YamlData.__init__(self, filename=f"{name}.yaml")
        self.name = name
        self._api_config = api_config_override

        data = self.get()
        if data and "data" in data:
            self.data = data["data"]
        else:
            self.data = data

    def __repr__(self):
        return f"CharacterState({self.name}): {self.data}"

    def get(self) -> dict[str, dict]:
        if self.data:
            return self.data

        chars: MyCharactersListSchema = get_my_characters_my_characters_get(
            api_config_override=self._api_config
        ).data  # FIXME: not async
        for char in chars:
            if char.name == self.name:
                self.data = char.dict()
                break
        return self.data

    def move_to(
        self,
        x: int,
        y: int,
    ) -> bool:
        """
        Move `name` to coords `x, y`
        """
        self._log.debug(f"Moving {self.name} to ({x},{y})")
        dest = DestinationSchema(x=x, y=y)
        response: CharacterMovementResponseSchema = (
            action_move_my__name__action_move_post(
                self.name, data=dest, api_config_override=self._api_config
            ).data
        )  # fixme: not async
        self._log.debug(f"Movement results {response}")
        return True  # TODO: return something useful from response

    def fight(self) -> bool:
        """fight in current location."""
        result: CharacterFightResponseSchema = action_fight_my__name__action_fight_post(
            name=char.name, api_config_override=apiconfig
        ).data
        self._log.debug(f"Fight results: {result}")
        # TODO: check fight results
        return True

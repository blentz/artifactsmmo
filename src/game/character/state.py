from src.lib.yaml_data import YamlData
from src.game.globals import DATA_PREFIX


class CharacterState(YamlData):
    """Character model."""

    name = None
    data = {}

    def __init__(self, data, name="character"):
        YamlData.__init__(self, filename=f"{DATA_PREFIX}/{name}.yaml")
        self.name = name
        self.data = data
        self.save()

    def __repr__(self):
        return f"CharacterState({self.name}): {self.data}"

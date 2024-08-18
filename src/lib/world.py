from .goap import World
from .yaml_data import GoapData, YamlData


class WorldState(GoapData):
    """World model."""

    world: World = None

    def __init__(self, filename: str = "world.yaml"):
        GoapData.__init__(self, filename=filename)
        self.world = World()
        for planner in self.planners:
            self.world.add_planner(planner)

    def save(self, **kwargs):
        """public interface for saving data to disk"""
        YamlData.save(self, **{"world": self.world._asdict(), **kwargs})

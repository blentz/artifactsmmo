from src.game.globals import DATA_PREFIX
from src.lib.goap import World
from src.lib.goap_data import GoapData


class WorldState(GoapData):
    """World model."""

    world = None

    def __init__(self, name="world"):
        GoapData.__init__(self, filename=f"{DATA_PREFIX}/{name}.yaml")
        self.world = World()
        for planner in self.planners:
            self.world.add_planner(planner)

    def save(self, **kwargs):
        """public interface for saving data to disk"""
        GoapData.save(self, **{"world": self.world._asdict(), **kwargs})

    def __repr__(self):
        return f"WorldState({self.name}): {self.world}"

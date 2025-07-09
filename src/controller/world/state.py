from src.game.globals import DATA_PREFIX
from src.lib.goap import World
from src.lib.goap_data import GoapData
from src.lib.unified_state_context import get_unified_context
from src.lib.state_parameters import StateParameters
from src.lib.yaml_data import YamlData
import logging


class WorldState(GoapData):
    """
    World model integrated with UnifiedStateContext.
    
    Provides bridge between GOAP planning system and unified flat state management.
    All state stored in flat format using StateParameters registry.
    """

    world = None
    _unified_context = None

    def __init__(self, name="world"):
        # Initialize logger first
        self._logger = logging.getLogger(__name__)
        self.world = World()
        self._unified_context = get_unified_context()
        
        # Initialize parent class (which calls load)
        GoapData.__init__(self, filename=f"{DATA_PREFIX}/{name}.yaml")
        
        for planner in self.planners:
            self.world.add_planner(planner)

    def load(self):
        """
        Load world state from flat YAML format.
        
        Loads flat state parameters directly into UnifiedStateContext.
        """
        # Clear existing planners
        self.planners = []
        
        # Load raw YAML data using parent's YamlData.load method
        data = YamlData.load(self) or {}
        
        # Load GOAP structure if present
        if isinstance(data, dict):
            self._load_planners(data.get("planners", []))
            
            # Load flat state parameters directly
            flat_params = {}
            self._logger.debug(f"Processing {len(data)} keys from YAML: {list(data.keys())}")
            
            for key, value in data.items():
                # Skip GOAP structure keys
                if key not in ['planners', 'world']:
                    # This is a flat state parameter
                    if StateParameters.validate_parameter(key):
                        flat_params[key] = value
                        self._logger.debug(f"Added flat parameter: {key} = {value}")
                    else:
                        self._logger.warning(f"Unknown parameter '{key}' ignored during load")
            
            # Load flat parameters into unified context
            if flat_params:
                self._unified_context.load_from_flat_dict(flat_params)
                self._logger.info(f"Loaded {len(flat_params)} flat state parameters")
            else:
                self._logger.warning("No flat state parameters found to load")

    def save(self, **kwargs):
        """
        Save world state using flat format.
        
        Exports unified state as flat YAML with dotted parameter names.
        """
        flat_state = self._unified_context.to_flat_dict()
        world_data = self.world._asdict()
        
        # Combine flat state with GOAP structure
        combined_data = {
            **flat_state,  # Flat parameters at root level
            "planners": self.planners,
            "world": world_data,
            **kwargs
        }
        
        # Save using parent class with flat structure
        super().save(**combined_data)
        self._logger.debug(f"Saved world state with {len(flat_state)} flat parameters")

    def load_flat_state(self, flat_data):
        """
        Load state from flat dictionary format.
        
        Args:
            flat_data: Dictionary with dotted parameter keys
        """
        if not flat_data:
            self._logger.warning("No flat state data to load")
            return
            
        self._unified_context.load_from_flat_dict(flat_data)
        self._logger.info(f"Loaded {len(flat_data)} parameters from flat state")

    def get_state_parameter(self, param):
        """
        Get state parameter using StateParameters registry.
        
        Args:
            param: Parameter name from StateParameters
            
        Returns:
            Parameter value or None
        """
        return self._unified_context.get(param)

    def set_state_parameter(self, param, value):
        """
        Set state parameter using StateParameters registry.
        
        Args:
            param: Parameter name from StateParameters
            value: Value to set
        """
        self._unified_context.set(param, value)

    def get_unified_context(self):
        """Get the unified state context instance."""
        return self._unified_context

    def __repr__(self):
        return f"WorldState({self.name}): {self.world}"

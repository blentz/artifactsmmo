from src.game.globals import DATA_PREFIX
from src.lib.yaml_data import YamlData


class CharacterState(YamlData):
    """
    Character model that stores data directly from API responses.
    
    No hardcoded slot mappings or equipment lists - data is stored
    exactly as received from the API.
    """

    name = None
    data = {}

    def __init__(self, data, name="character"):
        YamlData.__init__(self, filename=f"{DATA_PREFIX}/characters/{name}.yaml")
        self.name = name
        self.data = data if isinstance(data, dict) else {}
        self.save()
    
    def update_from_api_response(self, character_data):
        """
        Update character state from API response data.
        
        Args:
            character_data: Character data from API response
        """
        if not character_data:
            return
            
        # Dynamically update all attributes from API response
        for attr in dir(character_data):
            if not attr.startswith('_') and not attr.startswith('to_'):
                value = getattr(character_data, attr, None)
                # Only store serializable values (not methods or functions)
                if value is not None and not callable(value):
                    # Handle special cases
                    if attr == 'inventory' and hasattr(value, '__iter__'):
                        # Convert inventory items to dicts
                        self.data[attr] = []
                        for item in value:
                            if hasattr(item, 'to_dict'):
                                self.data[attr].append(item.to_dict())
                            elif hasattr(item, 'code') and hasattr(item, 'quantity'):
                                self.data[attr].append({'code': item.code, 'quantity': item.quantity})
                    elif hasattr(value, 'to_dict'):
                        # Convert complex objects to dict
                        self.data[attr] = value.to_dict()
                    else:
                        # Handle enum values by converting to string
                        if hasattr(value, 'value'):
                            # This is likely an enum, store its value
                            self.data[attr] = value.value
                        else:
                            # Store simple values directly
                            self.data[attr] = value

    def __repr__(self):
        return f"CharacterState({self.name}): {self.data}"

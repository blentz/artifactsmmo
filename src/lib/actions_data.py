""" actions_data module """

from src.lib.yaml_data import YamlData


class ActionsData(YamlData):
    """GOAP actions configuration data stored in YAML."""

    def __init__(self, filename="config/default_actions.yaml"):
        super().__init__(filename=filename)

    def get_actions(self):
        """
        Get the actions configuration from the YAML data.
        
        Returns:
            Dictionary of action configurations
        """
        return self.data.get('actions', {})

    def get_metadata(self):
        """
        Get metadata about the actions configuration.
        
        Returns:
            Dictionary containing metadata
        """
        return self.data.get('metadata', {})
    
    def get_state_defaults(self):
        """
        Get state defaults required by GOAP actions.
        
        Returns:
            Dictionary of state parameter defaults
        """
        return self.data.get('state_defaults', {})

    def get_goal_templates(self):
        """
        Get goal template configurations from the YAML data.
        
        Returns:
            Dictionary of goal template configurations
        """
        return self.data.get('goal_templates', {})

    def get_goal_template(self, goal_name: str):
        """
        Get a specific goal template by name.
        
        Args:
            goal_name: Name of the goal template to retrieve
            
        Returns:
            Dictionary containing the goal template, or None if not found
        """
        return self.get_goal_templates().get(goal_name)

    def __repr__(self):
        actions_count = len(self.get_actions())
        goals_count = len(self.get_goal_templates())
        return f"ActionsData({self.filename}): {actions_count} actions, {goals_count} goal templates loaded"
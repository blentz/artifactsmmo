"""
GOAP Goal Manager - Simplified Architecture-Compliant Version

Simple YAML-driven goal template provider. Business logic goes in actions.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from src.game.globals import CONFIG_PREFIX
from src.lib.yaml_data import YamlData


class GOAPGoalManager:
    """Simple YAML-driven goal template provider."""
    
    def __init__(self, config_file: str = None):
        self.logger = logging.getLogger(__name__)
        
        if config_file is None:
            config_file = f"{CONFIG_PREFIX}/goal_templates.yaml"
        
        self.config_data = YamlData(config_file)
        self._load_configuration()
        
    def _load_configuration(self) -> None:
        """Load goal templates and rules from YAML."""
        self.goal_templates = self.config_data.data.get('goal_templates', {})
        self.goal_selection_rules = self.config_data.data.get('goal_selection_rules', {})
        self.thresholds = self.config_data.data.get('thresholds', {})
    
    def select_goal(self, current_state: Dict[str, Any], 
                   available_goals: List[str] = None,
                   goal_weights: Dict[str, float] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Select goal using YAML rules in priority order."""
        if available_goals is None:
            available_goals = list(self.goal_templates.keys())
        
        # Collect all rules with priorities
        all_rules = []
        for category_name, rules in self.goal_selection_rules.items():
            for rule in rules:
                all_rules.append({
                    'category': category_name,
                    'rule': rule,
                    'priority': rule.get('priority', 0),
                    'goal_name': rule.get('goal')
                })
        
        # Sort by priority (highest first)
        all_rules.sort(key=lambda x: x['priority'], reverse=True)
        
        # Check each rule in priority order
        for rule_data in all_rules:
            rule = rule_data['rule']
            goal_name = rule_data['goal_name']
            
            if goal_name not in available_goals:
                continue
                
            goal_config = self.goal_templates.get(goal_name)
            if not goal_config:
                continue
            
            # Check simple boolean conditions
            if self._check_condition(rule.get('condition', {}), current_state):
                return (goal_name, goal_config)
        
        return None
    
    def _check_condition(self, condition: Dict[str, Any], state: Dict[str, Any]) -> bool:
        """Check simple boolean/string conditions."""
        for key, expected_value in condition.items():
            actual_value = state.get(key)
            
            if isinstance(expected_value, list):
                if actual_value not in expected_value:
                    return False
            elif isinstance(expected_value, str):
                if expected_value.startswith('>='):
                    if float(actual_value) < float(expected_value[2:]):
                        return False
                elif expected_value.startswith('<='):
                    if float(actual_value) > float(expected_value[2:]):
                        return False
                elif expected_value.startswith('<'):
                    if float(actual_value) >= float(expected_value[1:]):
                        return False
                elif expected_value.startswith('>'):
                    if float(actual_value) <= float(expected_value[1:]):
                        return False
                elif expected_value == "!null":
                    if actual_value is None:
                        return False
                elif expected_value == "null":
                    if actual_value is not None:
                        return False
                else:
                    if str(actual_value) != expected_value:
                        return False
            else:
                if actual_value != expected_value:
                    return False
                    
        return True
    
    def generate_goal_state(self, goal_name: str, goal_config: Dict[str, Any], 
                          current_state: Dict[str, Any], **parameters) -> Dict[str, Any]:
        """Generate GOAP goal state from template."""
        return goal_config.get('target_state', {}).copy()
    
    def get_goal_strategy(self, goal_name: str, goal_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get strategy configuration for a goal."""
        strategy = goal_config.get('strategy', {}).copy()
        strategy.setdefault('max_iterations', self.thresholds.get('max_goap_iterations', 50))
        strategy.setdefault('hunt_radius', self.thresholds.get('default_search_radius', 8))
        strategy.setdefault('safety_priority', True)
        return strategy
    
    def get_threshold(self, key: str, default: Any = None) -> Any:
        """Get threshold value."""
        return self.thresholds.get(key, default)
    
    def reload_configuration(self) -> None:
        """Reload configuration."""
        self.config_data.load()
        self._load_configuration()
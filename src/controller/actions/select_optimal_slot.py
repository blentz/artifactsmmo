"""
Select Optimal Slot Action

This action selects the optimal equipment slot for crafting based on:
- Equipment gap analysis from AnalyzeEquipmentGapsAction
- Target crafting skill from goal parameters
- Slot priority weights from configuration
"""

import logging
from typing import Dict, List, Tuple

from src.controller.actions.base import ActionBase
from src.game.globals import CONFIG_PREFIX
from src.lib.action_context import ActionContext
from src.lib.yaml_data import YamlData


class SelectOptimalSlotAction(ActionBase):
    """
    Action to select the optimal equipment slot for crafting skill XP.
    
    This action combines equipment gap analysis with slot priority weights
    and crafting skill constraints to select the best slot for crafting.
    """
    
    # GOAP parameters
    conditions = {
        'equipment_gaps_analyzed': True,
        'character_alive': True
    }
    
    reactions = {
        'optimal_slot_selected': True,
        'target_slot_specified': True
    }
    
    weight = 1.5
    
    def __init__(self):
        """Initialize the slot selection action."""
        super().__init__()
        self.config = None
        
    def _load_equipment_config(self) -> YamlData:
        """Load equipment analysis configuration from YAML."""
        if self.config is None:
            try:
                self.config = YamlData(f"{CONFIG_PREFIX}/equipment_analysis.yaml")
                self.logger.debug("Loaded equipment analysis configuration for slot selection")
            except Exception as e:
                self.logger.error(f"Failed to load equipment analysis config: {e}")
                # Provide fallback configuration
                self.config = self._get_fallback_config()
        return self.config
        
    def _get_fallback_config(self) -> YamlData:
        """Provide fallback configuration if YAML loading fails."""
        fallback_data = {
            'skill_slot_mappings': {
                'weaponcrafting': ['weapon'],
                'gearcrafting': ['helmet', 'body_armor', 'leg_armor', 'boots'],
                'jewelrycrafting': ['amulet', 'ring1', 'ring2']
            },
            'slot_priorities': {
                'weapon': 100,
                'helmet': 80,
                'body_armor': 85,
                'leg_armor': 75,
                'boots': 70,
                'amulet': 60,
                'ring1': 50,
                'ring2': 50
            }
        }
        config = YamlData.__new__(YamlData)
        config.data = fallback_data
        return config
        
    def execute(self, client, context: ActionContext) -> Dict:
        """
        Execute slot selection based on equipment gaps and target skill.
        
        Args:
            client: API client (not used for this selection)
            context: ActionContext containing gap analysis and target skill
            
        Returns:
            Action result with selected slot information
        """
        super().execute(client, context)
        
        # Get required data from context
        gap_analysis = context.get_parameter('equipment_gap_analysis')
        target_skill = context.get_parameter('target_craft_skill')
        
        if not target_skill:
            return self.get_error_response("Target craft skill not specified")
            
        if not gap_analysis:
            return self.get_error_response("Equipment gap analysis not available - run AnalyzeEquipmentGapsAction first")
            
        config = self._load_equipment_config()
        
        # Get applicable slots for the target crafting skill
        applicable_slots = config.data.get('skill_slot_mappings', {}).get(target_skill, [])
        
        if not applicable_slots:
            return self.get_error_response(f"No equipment slots mapped for skill '{target_skill}'")
            
        self.logger.info(f"🎯 Selecting optimal slot for {target_skill} from {len(applicable_slots)} options")
        
        # Calculate combined scores for each applicable slot
        slot_scores = []
        for slot in applicable_slots:
            score_data = self._calculate_slot_score(slot, gap_analysis, config)
            if score_data:
                slot_scores.append(score_data)
                self.logger.debug(f"  {slot}: combined score {score_data['combined_score']:.2f} "
                                f"(gap: {score_data['gap_score']:.1f}, priority: {score_data['priority_weight']})")
        
        # Select the highest scoring slot
        if not slot_scores:
            return self.get_error_response(f"No valid slots found for skill {target_skill}")
            
        # Sort by combined score (highest first)
        slot_scores.sort(key=lambda x: x['combined_score'], reverse=True)
        best_slot_data = slot_scores[0]
        
        # Store results in context for next action
        context.set_result('target_equipment_slot', best_slot_data['slot_name'])
        context.set_result('slot_selection_reasoning', {
            'selected_slot': best_slot_data['slot_name'],
            'target_skill': target_skill,
            'combined_score': best_slot_data['combined_score'],
            'gap_score': best_slot_data['gap_score'],
            'priority_weight': best_slot_data['priority_weight'],
            'urgency_reason': best_slot_data['urgency_reason'],
            'alternatives': [
                {
                    'slot': data['slot_name'],
                    'score': data['combined_score'],
                    'reason': data['urgency_reason']
                }
                for data in slot_scores[1:4]  # Top 3 alternatives
            ]
        })
        
        # Set additional context flags
        context.set_result('optimal_slot_selected', True)
        context.set_result('target_slot_specified', True)
        
        self.logger.info(f"✅ Selected '{best_slot_data['slot_name']}' for {target_skill} crafting "
                        f"(score: {best_slot_data['combined_score']:.2f}, reason: {best_slot_data['urgency_reason']})")
        
        return self.get_success_response(
            selected_slot=best_slot_data['slot_name'],
            target_skill=target_skill,
            combined_score=best_slot_data['combined_score'],
            gap_score=best_slot_data['gap_score'],
            priority_weight=best_slot_data['priority_weight'],
            alternatives_considered=len(slot_scores)
        )
        
    def _calculate_slot_score(self, slot_name: str, gap_analysis: Dict, 
                             config: YamlData) -> Dict:
        """
        Calculate combined score for a slot based on gap urgency and priority.
        
        Args:
            slot_name: Name of the equipment slot
            gap_analysis: Equipment gap analysis data
            config: Equipment analysis configuration
            
        Returns:
            Dictionary with slot scoring data, or None if slot not in analysis
        """
        if slot_name not in gap_analysis:
            self.logger.warning(f"Slot '{slot_name}' not found in gap analysis")
            return None
            
        slot_gap_data = gap_analysis[slot_name]
        gap_score = slot_gap_data.get('urgency_score', 0)
        urgency_reason = slot_gap_data.get('reason', 'unknown')
        
        # Get priority weight from configuration
        slot_priorities = config.data.get('slot_priorities', {})
        priority_weight = slot_priorities.get(slot_name, 50)  # Default weight of 50
        
        # Calculate combined score
        # Formula: gap_urgency * (priority_weight / 100)
        # This gives higher priority to urgent gaps in high-priority slots
        combined_score = gap_score * (priority_weight / 100)
        
        return {
            'slot_name': slot_name,
            'combined_score': combined_score,
            'gap_score': gap_score,
            'priority_weight': priority_weight,
            'urgency_reason': urgency_reason,
            'missing_equipment': slot_gap_data.get('missing', False),
            'level_difference': slot_gap_data.get('level_difference', 0)
        }
        
    def get_slot_selection_summary(self, context: ActionContext) -> Dict:
        """
        Get a summary of the slot selection process for debugging.
        
        Args:
            context: ActionContext containing selection results
            
        Returns:
            Summary dictionary with selection details
        """
        reasoning = context.get_parameter('slot_selection_reasoning', {})
        
        return {
            'selected_slot': reasoning.get('selected_slot'),
            'target_skill': reasoning.get('target_skill'),
            'selection_score': reasoning.get('combined_score'),
            'selection_reason': reasoning.get('urgency_reason'),
            'alternatives': reasoning.get('alternatives', [])
        }
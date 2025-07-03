"""
Analyze Equipment Gaps Action

This action performs comprehensive equipment analysis for all slots,
calculating upgrade urgency scores and identifying equipment priorities.
"""

from typing import Any, Dict, Optional

from src.controller.actions.base import ActionBase
from src.game.character.state import CharacterState
from src.game.globals import CONFIG_PREFIX
from src.lib.action_context import ActionContext
from src.lib.yaml_data import YamlData


class AnalyzeEquipmentGapsAction(ActionBase):
    """
    Action to analyze all equipment slots and calculate upgrade priorities.
    
    This action examines every equipment slot, compares current equipment
    to character level and stats, and generates urgency scores for upgrades.
    Results are stored in ActionContext for use by subsequent actions.
    """
    
    # GOAP parameters
    conditions = {
            'equipment_status': {
                'upgrade_status': 'analyzing',
            },
            'character_status': {
                'alive': True,
            },
        }
    
    reactions = {
        'equipment_status': {
            'upgrade_status': 'analyzing',  # Default, will be overridden to 'combat_ready' if appropriate
            'gaps_analyzed': True
        }
    }
    
    weight = 1.0
    
    def __init__(self):
        """Initialize the equipment gap analysis action."""
        super().__init__()
        self.config = None
        
    def _load_equipment_config(self) -> YamlData:
        """Load equipment analysis configuration from YAML."""
        if self.config is None:
            try:
                self.config = YamlData(f"{CONFIG_PREFIX}/equipment_analysis.yaml")
                self.logger.debug(f"Loaded equipment analysis configuration with {len(self.config.data)} sections")
            except Exception as e:
                self.logger.error(f"Failed to load equipment analysis config: {e}")
                # Provide fallback configuration
                self.config = self._get_fallback_config()
        return self.config
        
    def _get_fallback_config(self) -> YamlData:
        """Provide fallback configuration if YAML loading fails."""
        fallback_data = {
            'all_equipment_slots': ['weapon', 'helmet', 'body_armor', 'leg_armor', 'boots'],
            'gap_analysis': {
                'level_penalties': {
                    'missing_item': 100,
                    'level_behind_1': 20,
                    'level_behind_2': 40,
                    'level_behind_3': 60,
                    'level_ahead': -10
                }
            }
        }
        config = YamlData.__new__(YamlData)
        config.data = fallback_data
        return config
        
    def execute(self, client, context: ActionContext) -> Dict:
        """
        Execute equipment gap analysis for all slots.
        
        Args:
            client: API client (not used for this analysis)
            context: ActionContext containing character state
            
        Returns:
            Action result with equipment gap analysis
        """
        super().execute(client, context)
        
        character_state = context.character_state
        if not character_state:
            return self.get_error_response("No character state available")
            
        config = self._load_equipment_config()
        
        # Analyze all equipment slots
        gap_analysis = {}
        all_slots = config.data.get('all_equipment_slots', [])
        
        self.logger.info(f"🔍 Analyzing equipment gaps for {len(all_slots)} slots")
        
        for slot_name in all_slots:
            try:
                gap_data = self._analyze_slot_gap(character_state, slot_name, config)
                gap_analysis[slot_name] = gap_data
                self.logger.debug(f"  {slot_name}: urgency {gap_data['urgency_score']:.1f} "
                                f"({gap_data['reason']})")
            except Exception as e:
                self.logger.warning(f"Failed to analyze slot {slot_name}: {e}")
                gap_analysis[slot_name] = {
                    'urgency_score': 50,
                    'current_level': 0,
                    'char_level': character_state.data.get('level', 1),
                    'missing': True,
                    'reason': 'analysis_failed',
                    'error': str(e)
                }
        
        # Store results in context for subsequent actions
        context.set_result('equipment_gap_analysis', gap_analysis)
        # Store timestamp for cache invalidation
        from datetime import datetime, timezone
        context.set_result('equipment_analysis_timestamp', datetime.now(timezone.utc).isoformat())
        
        # Calculate summary statistics
        total_urgency = sum(slot['urgency_score'] for slot in gap_analysis.values())
        avg_urgency = total_urgency / len(gap_analysis) if gap_analysis else 0
        missing_slots = sum(1 for slot in gap_analysis.values() if slot['missing'])
        
        self.logger.info(f"📊 Equipment analysis complete: {missing_slots} missing slots, "
                        f"average urgency {avg_urgency:.1f}")
        
        # Determine if equipment is combat ready
        # Check if all critical slots have adequate or excellent equipment
        critical_slots = ['weapon']  # Can expand to include armor slots
        is_combat_ready = True
        
        for slot_name in critical_slots:
            if slot_name in gap_analysis:
                slot_data = gap_analysis[slot_name]
                reason = slot_data.get('reason', '')
                # Check if equipment is adequate or excellent
                if reason not in ['adequate equipment', 'excellent stats, low urgency', 'equipment ahead of character level']:
                    is_combat_ready = False
                    break
        
        # Update reactions based on analysis
        if is_combat_ready:
            self.reactions = {
                'equipment_status': {
                    'upgrade_status': 'combat_ready',
                    'gaps_analyzed': True
                }
            }
            self.logger.info("✅ Equipment is combat ready!")
        else:
            # Keep default reactions (upgrade_status: 'analyzing')
            pass
        
        return self.get_success_response(
            slots_analyzed=len(gap_analysis),
            missing_slots=missing_slots,
            average_urgency=avg_urgency,
            total_urgency=total_urgency,
            is_combat_ready=is_combat_ready
        )
        
    def _analyze_slot_gap(self, character_state: CharacterState, slot_name: str, 
                         config: YamlData) -> Dict[str, Any]:
        """
        Analyze a specific equipment slot for upgrade urgency.
        
        Args:
            character_state: Current character state
            slot_name: Name of equipment slot to analyze
            config: Equipment analysis configuration
            
        Returns:
            Dictionary containing gap analysis data
        """
        current_item = self._get_current_equipment(character_state, slot_name)
        char_level = character_state.data.get('level', 1)
        
        # Handle missing equipment (empty slot)
        if not current_item:
            return {
                'urgency_score': config.data['gap_analysis']['level_penalties']['missing_item'],
                'current_level': 0,
                'char_level': char_level,
                'missing': True,
                'reason': 'empty_slot',
                'slot_type': self._categorize_slot(slot_name)
            }
        
        # Analyze existing equipment
        item_level = current_item.get('level', 1)
        level_diff = char_level - item_level
        
        # Calculate urgency based on level difference
        urgency_score = self._calculate_urgency_score(level_diff, config)
        
        # Apply stat-based modifiers
        stat_modifier = self._calculate_stat_modifier(current_item, slot_name, config)
        final_urgency = max(0, min(100, urgency_score + stat_modifier))
        
        return {
            'urgency_score': final_urgency,
            'current_level': item_level,
            'char_level': char_level,
            'missing': False,
            'level_difference': level_diff,
            'stat_modifier': stat_modifier,
            'reason': self._get_urgency_reason(level_diff, stat_modifier),
            'slot_type': self._categorize_slot(slot_name),
            'current_item_code': current_item.get('code', 'unknown')
        }
        
    def _get_current_equipment(self, character_state: CharacterState, slot: str) -> Optional[Dict]:
        """Get the current equipment in the specified slot."""
        # Get equipment from world state via context, not character state
        if hasattr(self, '_context') and self._context:
            equipment_status = self._context.get('equipment_status', {})
            item_code = equipment_status.get(slot)
            
            if item_code:
                # Return equipment info with proper level
                item_level = self._get_item_level(item_code)
                return {'code': item_code, 'level': item_level}
            return None
        
        # Fallback to checking character slots directly from character data
        if not character_state.data:
            return None
            
        # Check slot fields in character data (e.g., weapon_slot, helmet_slot)
        slot_field = f"{slot}_slot"
        item_code = character_state.data.get(slot_field)
        
        if item_code:
            # Return basic item info with proper level
            item_level = self._get_item_level(item_code)
            return {'code': item_code, 'level': item_level}
            
        return None
    
    def _get_item_level(self, item_code: str) -> int:
        """Get the level of an item by its code."""
        # Known item levels for common equipment
        item_levels = {
            # Starter weapons
            'wooden_stick': 1,
            'wooden_staff': 1,
            
            # Basic weapons
            'copper_dagger': 1,
            'iron_sword': 5,
            'iron_shield': 4,
            
            # Basic armor
            'leather_armor': 1,
            'leather_helmet': 1,
            'iron_helmet': 4,
            'iron_armor': 5,
            'iron_boots': 3,
            
            # Accessories
            'silver_ring': 4,
            'copper_ring': 1,
        }
        
        return item_levels.get(item_code, 1)  # Default to level 1 if unknown
            
    def _calculate_urgency_score(self, level_diff: int, config: YamlData) -> float:
        """Calculate urgency score based on level difference."""
        penalties = config.data['gap_analysis']['level_penalties']
        
        if level_diff <= -1:  # Item is ahead of character level
            return penalties.get('level_ahead', -10)
        elif level_diff == 1:
            return penalties.get('level_behind_1', 20)
        elif level_diff == 2:
            return penalties.get('level_behind_2', 40)
        elif level_diff >= 3:
            return penalties.get('level_behind_3', 60)
        else:  # level_diff == 0, item matches character level
            return 10  # Low urgency for current-level equipment
            
    def _calculate_stat_modifier(self, item: Dict, slot_name: str, config: YamlData) -> float:
        """Calculate stat-based urgency modifier."""
        slot_type = self._categorize_slot(slot_name)
        stat_weights = config.data.get('gap_analysis', {}).get('stat_weights', {}).get(slot_type, {})
        
        if not stat_weights:
            return 0
            
        item_effects = item.get('effects', {})
        if not item_effects:
            return 5  # Slight urgency increase for items with no effects
            
        # Calculate weighted stat score
        total_weighted_stats = 0
        total_weight = 0
        
        for stat, weight in stat_weights.items():
            stat_value = item_effects.get(stat, 0)
            if stat_value > 0:
                total_weighted_stats += stat_value * weight
                total_weight += weight
                
        if total_weight == 0:
            return 5  # No relevant stats found
            
        # Convert to urgency modifier (lower stats = higher urgency)
        avg_weighted_stat = total_weighted_stats / total_weight
        
        # Modifier ranges from -5 to +15 based on stat quality
        if avg_weighted_stat >= 30:
            return -5  # Great stats, lower urgency
        elif avg_weighted_stat >= 20:
            return 0   # Good stats, no modifier
        elif avg_weighted_stat >= 10:
            return 5   # Mediocre stats, slight urgency
        else:
            return 15  # Poor/no stats, higher urgency
            
    def _categorize_slot(self, slot_name: str) -> str:
        """Categorize slot for stat weight lookup."""
        if slot_name in ['weapon', 'shield']:
            return 'weapon'
        elif slot_name in ['helmet', 'body_armor', 'leg_armor', 'boots']:
            return 'armor'
        elif slot_name in ['amulet', 'ring1', 'ring2']:
            return 'accessory'
        elif slot_name == 'consumable':
            return 'consumable'
        elif slot_name == 'potion':
            return 'potion'
        else:
            return 'unknown'
            
    def _get_urgency_reason(self, level_diff: int, stat_modifier: float) -> str:
        """Generate human-readable reason for urgency score."""
        if level_diff >= 3:
            return f"equipment {level_diff} levels behind"
        elif level_diff == 2:
            return "equipment 2 levels behind"
        elif level_diff == 1:
            return "equipment 1 level behind"
        elif level_diff <= -1:
            return "equipment ahead of character level"
        elif stat_modifier > 10:
            return "poor stats for slot"
        elif stat_modifier < 0:
            return "excellent stats, low urgency"
        else:
            return "adequate equipment"
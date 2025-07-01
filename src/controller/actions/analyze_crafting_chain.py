"""
Comprehensive Crafting Chain Analysis Action

This action recursively examines the entire crafting dependency chain from raw materials
to final equipment, mapping out resource nodes, workshops, and intermediate steps.
"""

from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

from artifactsmmo_api_client.api.items.get_item_items_code_get import sync as get_item_api

from .base import ActionBase

if TYPE_CHECKING:
    from src.lib.action_context import ActionContext


class AnalyzeCraftingChainAction(ActionBase):
    """ Action to analyze complete crafting dependency chains """

    # GOAP parameters
    conditions = {"character_alive": True}
    reactions = {"craft_plan_available": True, "material_requirements_known": True, "crafting_opportunities_known": True}
    weights = {"craft_plan_available": 20}

    def __init__(self):
        """
        Initialize the crafting chain analysis action.
        """
        super().__init__()
        
        # Chain analysis data
        self.analyzed_items: Set[str] = set()
        self.resource_nodes: Dict[str, Dict] = {}
        self.workshops: Dict[str, Dict] = {}
        self.crafting_dependencies: Dict[str, List[Dict]] = {}
        self.transformation_chains: List[Dict] = []

    def execute(self, client, context: 'ActionContext') -> Optional[Dict]:
        """ Analyze the complete crafting chain for the target item """
        if not self.validate_execution_context(client, context):
            return self.get_error_response("No API client provided")
            
        # Get character name and target item from context
        character_name = context.character_name
        if not character_name:
            return self.get_error_response("No character name provided")
            
        target_item = context.get('target_item')
        if not target_item:
            return self.get_error_response("No target item specified for analysis")
            
        self.log_execution_start(character_name=character_name, target_item=target_item)
        
        try:
            # Get knowledge base and map state from context
            knowledge_base = context.knowledge_base
            map_state = context.map_state
            
            # Get character inventory from context
            self.character_inventory = context.get_character_inventory() if hasattr(context, 'get_character_inventory') else {}
            
            # Store context for use in helper methods
            self.current_context = context
            
            # Start recursive analysis from target item
            chain_analysis = self._analyze_complete_chain(client, target_item, knowledge_base)
            
            if not chain_analysis:
                return self.get_error_response(f"Could not analyze crafting chain for {target_item}")
            
            # Build complete action sequence
            action_sequence = self._build_action_sequence(chain_analysis, knowledge_base, map_state, client)
            
            result = {
                'success': True,
                'target_item': target_item,
                'chain_analysis': chain_analysis,
                'action_sequence': action_sequence,
                'resource_nodes_required': self.resource_nodes,
                'workshops_required': self.workshops,
                'total_steps': len(action_sequence),
                'raw_materials_needed': self._extract_raw_materials(chain_analysis)
            }
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Crafting chain analysis failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def _analyze_complete_chain(self, client, item_code: str, knowledge_base, depth: int = 0) -> Optional[Dict]:
        """
        Recursively analyze the complete crafting chain for an item.
        
        Uses existing knowledge when available, only makes API calls when necessary.
        Returns a tree structure representing the full dependency chain.
        """
        if depth > 10:  # Prevent infinite recursion
            self.logger.warning(f"Maximum recursion depth reached for {item_code}")
            return None
            
        if item_code in self.analyzed_items:
            return {"item_code": item_code, "type": "already_analyzed"}
            
        self.analyzed_items.add(item_code)
        
        # First try to get item details from knowledge base
        item_data = self._get_item_from_knowledge(item_code, knowledge_base)
        
        # If not in knowledge base, make API call
        if not item_data:
            item_response = get_item_api(code=item_code, client=client)
            if not item_response or not item_response.data:
                return None
            item_data = item_response.data
        
        # Check if this is a craftable item (handle both API objects and knowledge base dictionaries)
        craft_data = None
        if isinstance(item_data, dict):
            # Knowledge base data
            craft_data = item_data.get('craft_data')
        else:
            # API response object
            if hasattr(item_data, 'craft'):
                craft_data = item_data.craft
        
        if not craft_data:
            # This is a base resource - check if it can be gathered
            return self._analyze_resource_chain(item_code, item_data, knowledge_base)
        
        # This is a craftable item - analyze its dependencies
        required_materials = []
        
        # Handle both knowledge base and API formats
        craft_items = []
        if isinstance(craft_data, dict):
            # Knowledge base format
            craft_items = craft_data.get('items', [])
        else:
            # API format
            if hasattr(craft_data, 'items'):
                craft_items = craft_data.items
        
        for material_info in craft_items:
            if isinstance(material_info, dict):
                # Knowledge base format
                material_code = material_info.get('code', '')
                quantity = material_info.get('quantity', 1)
            else:
                # API format
                material_code = material_info.code
                quantity = material_info.quantity
                
            # Recursively analyze each required material
            material_chain = self._analyze_complete_chain(client, material_code, knowledge_base, depth + 1)
            if material_chain:
                required_materials.append({
                    'material_code': material_code,
                    'quantity_required': quantity,
                    'chain': material_chain
                })
        
        # Determine workshop requirements
        if isinstance(craft_data, dict):
            craft_skill = craft_data.get('skill', 'unknown')
        else:
            craft_skill = getattr(craft_data, 'skill', 'unknown')
        
        workshop_type = self._skill_to_workshop_type(craft_skill, knowledge_base)
        
        # Get item name and level
        if isinstance(item_data, dict):
            item_name = item_data.get('name', item_code)
            level_required = item_data.get('level', 1)
        else:
            item_name = getattr(item_data, 'name', item_code)
            level_required = getattr(item_data, 'level', 1)
        
        return {
            'item_code': item_code,
            'item_name': item_name,
            'type': 'craftable',
            'craft_skill': craft_skill,
            'workshop_type': workshop_type,
            'level_required': level_required,
            'required_materials': required_materials,
            'total_materials_needed': self._calculate_total_materials(required_materials)
        }

    def _analyze_resource_chain(self, resource_code: str, item_data, knowledge_base) -> Dict:
        """
        Analyze a base resource to determine gathering requirements.
        """
        # Check if this is a raw material that needs transformation
        transformation = self._check_transformation_needed(resource_code, knowledge_base)
        
        # Get item name handling both formats
        if isinstance(item_data, dict):
            item_name = item_data.get('name', resource_code)
        else:
            item_name = getattr(item_data, 'name', resource_code)
        
        if transformation:
            return {
                'item_code': resource_code,
                'item_name': item_name,
                'type': 'transformable_resource',
                'raw_material': transformation['raw_material'],
                'workshop_type': transformation['workshop_type'],
                'gathering_info': self._get_gathering_info(transformation['raw_material'], knowledge_base)
            }
        else:
            return {
                'item_code': resource_code,
                'item_name': item_name,
                'type': 'base_resource',
                'gathering_info': self._get_gathering_info(resource_code, knowledge_base)
            }

    def _check_transformation_needed(self, item_code: str, knowledge_base=None) -> Optional[Dict]:
        """
        Check if an item requires transformation from a raw material using API data.
        
        This method determines transformation requirements by looking up the item's recipe
        in the knowledge base. If the item has a recipe that requires raw materials,
        it's considered a transformable resource.
        """
        if not knowledge_base or not hasattr(knowledge_base, 'data'):
            self.logger.warning(f"⚠️ No knowledge base available for transformation lookup of {item_code}")
            return None
        
        items = knowledge_base.data.get('items', {})
        if item_code not in items:
            return None
        
        item_info = items[item_code]
        craft_data = item_info.get('craft_data', {})
        
        if not craft_data:
            return None
        
        # Get the crafting skill to determine workshop type
        craft_skill = craft_data.get('skill', '')
        workshop_type = self._skill_to_workshop_type(craft_skill, knowledge_base)
        
        # Get the raw materials required
        craft_items = craft_data.get('items', [])
        if not craft_items:
            return None
        
        # For transformation materials, typically there's one primary raw material
        # Take the first (and usually only) required material
        primary_material = craft_items[0]
        raw_material_code = primary_material.get('code', '')
        
        if raw_material_code:
            self.logger.info(f"📊 Found transformation from API: {raw_material_code} → {item_code} at {workshop_type} workshop")
            return {
                'raw_material': raw_material_code,
                'workshop_type': workshop_type
            }
        
        return None

    def _get_gathering_info(self, resource_code: str, knowledge_base) -> Dict:
        """
        Get information about where and how to gather a resource.
        """
        gathering_info = {
            'resource_code': resource_code,
            'known_locations': [],
            'skill_required': 'unknown',
            'level_required': 1
        }
        
        if knowledge_base and hasattr(knowledge_base, 'data'):
            # Check known resource locations
            resources = knowledge_base.data.get('resources', {})
            if resource_code in resources:
                resource_data = resources[resource_code]
                gathering_info.update({
                    'skill_required': resource_data.get('skill_required', 'unknown'),
                    'level_required': resource_data.get('level_required', 1)
                })
        
        return gathering_info

    def _skill_to_workshop_type(self, craft_skill: str, knowledge_base=None) -> str:
        """
        Map crafting skills to workshop types using API data.
        
        This method attempts to determine the workshop type by looking at workshops
        and facilities in the knowledge base. If not found, falls back to basic skill mapping.
        """
        if not craft_skill:
            return 'unknown'
        
        skill_lower = craft_skill.lower()
        
        # Try to get workshop type from knowledge base
        if knowledge_base and hasattr(knowledge_base, 'data'):
            # First check workshops section
            workshops = knowledge_base.data.get('workshops', {})
            for workshop_code, workshop_data in workshops.items():
                workshop_craft_skill = workshop_data.get('craft_skill', '').lower()
                facility_type = workshop_data.get('facility_type', '')
                
                if workshop_craft_skill == skill_lower and facility_type == 'workshop':
                    self.logger.info(f"📊 Found workshop type from workshops: {skill_lower} → {workshop_code}")
                    return workshop_code
            
            # Then check facilities section (for backward compatibility)
            facilities = knowledge_base.data.get('facilities', {})
            for facility_code, facility_data in facilities.items():
                facility_craft_skill = facility_data.get('craft_skill', '').lower()
                facility_type = facility_data.get('facility_type', '')
                
                if facility_craft_skill == skill_lower and facility_type == 'workshop':
                    self.logger.info(f"📊 Found workshop type from facilities: {skill_lower} → {facility_code}")
                    return facility_code
        
        # No hardcoded fallback - if not found in knowledge base, return the skill as-is
        # This forces the system to rely on API data only
        self.logger.warning(f"⚠️ Workshop type not found in knowledge base for skill: {skill_lower}")
        return skill_lower

    def _get_equipment_slot(self, item_code: str, workshop_type: str, knowledge_base=None, client=None) -> Optional[str]:
        """
        Determine the equipment slot for an item using API data.
        
        This method uses the knowledge base's get_item_data method which has API fallback
        to ensure we always get the most accurate item type information.
        """
        if not item_code:
            return None
        
        # Use knowledge base to get item data with API fallback
        if knowledge_base and hasattr(knowledge_base, 'get_item_data'):
            item_data = knowledge_base.get_item_data(item_code, client=client)
            if item_data:
                # First check for explicit slot information
                slot_info = item_data.get('slot', '')
                if slot_info and slot_info != 'unknown':
                    self.logger.info(f"📊 Found explicit slot from API: {item_code} → {slot_info}")
                    return slot_info
                
                # Then check item type
                item_type = item_data.get('type', '').lower()
                
                # Map item types to equipment slots
                if item_type == 'weapon':
                    self.logger.info(f"📊 API data: {item_code} is weapon type → weapon slot")
                    return 'weapon'
                elif item_type == 'shield':
                    self.logger.info(f"📊 API data: {item_code} is shield type → shield slot")
                    return 'shield'
                elif item_type == 'helmet':
                    self.logger.info(f"📊 API data: {item_code} is helmet type → helmet slot")
                    return 'helmet'
                elif item_type == 'body_armor':
                    self.logger.info(f"📊 API data: {item_code} is body_armor type → body_armor slot")
                    return 'body_armor'
                elif item_type == 'leg_armor':
                    self.logger.info(f"📊 API data: {item_code} is leg_armor type → leg_armor slot")
                    return 'leg_armor'
                elif item_type == 'boots':
                    self.logger.info(f"📊 API data: {item_code} is boots type → boots slot")
                    return 'boots'
                elif item_type == 'ring':
                    self.logger.info(f"📊 API data: {item_code} is ring type → ring1 slot")
                    return 'ring1'  # Default to first ring slot
                elif item_type == 'amulet':
                    self.logger.info(f"📊 API data: {item_code} is amulet type → amulet slot")
                    return 'amulet'
                elif item_type == 'artifact':
                    self.logger.info(f"📊 API data: {item_code} is artifact type → artifact1 slot")
                    return 'artifact1'  # Default to first artifact slot
                elif item_type and item_type not in ['consumable', 'resource', 'unknown']:
                    # Use the item type as slot name if it's equipment
                    self.logger.info(f"📊 API data: {item_code} ({item_type}) → {item_type} slot")
                    return item_type
        
        # No equipment slot found
        self.logger.warning(f"⚠️ No equipment slot found for {item_code} (workshop: {workshop_type})")
        return None

    def _calculate_total_materials(self, materials: List[Dict]) -> Dict[str, int]:
        """
        Calculate total quantities of all materials needed recursively.
        """
        totals = {}
        
        for material in materials:
            quantity = material['quantity_required']
            chain = material.get('chain', {})
            
            if chain.get('type') == 'base_resource' or chain.get('type') == 'transformable_resource':
                # This is a base material
                material_code = material['material_code']
                totals[material_code] = totals.get(material_code, 0) + quantity
            elif chain.get('type') == 'craftable':
                # This is a craftable item - recurse into its materials
                sub_materials = chain.get('total_materials_needed', {})
                for sub_code, sub_quantity in sub_materials.items():
                    totals[sub_code] = totals.get(sub_code, 0) + (sub_quantity * quantity)
        
        return totals

    def _build_action_sequence(self, chain_analysis: Dict, knowledge_base, map_state, client=None) -> List[Dict]:
        """
        Build a recipe-driven action sequence based on inventory state analysis.
        
        Recipe Resolution Order:
        1. Pick recipe (copper_dagger)
        2. Analyze recipe requirements (6 copper)
        3. Check inventory for ingredients (1 copper available, need 5 more)
        4. Analyze what provides missing ingredients (mining workshop: copper_ore → copper)
        5. Seek raw materials (need 50 more copper_ore for 5 copper)
        6. Transform raw materials (copper_ore → copper at mining workshop)
        7. Craft final item (copper → copper_dagger at weaponcrafting workshop)
        """
        actions = []
        
        # Recipe-driven approach: start with the target item
        target_item = chain_analysis.get('item_code')
        required_materials = chain_analysis.get('required_materials', [])
        
        self.logger.info(f"🔧 Building recipe-driven action sequence for {target_item}")
        
        # For each required material, check inventory and resolve shortfalls
        for material in required_materials:
            material_code = material['material_code']
            quantity_needed = material['quantity_required']
            
            # Check current inventory
            current_quantity = self.character_inventory.get(material_code, 0)
            shortage = max(0, quantity_needed - current_quantity)
            
            if shortage > 0:
                self.logger.info(f"📦 Need {shortage} more {material_code} (have {current_quantity}, need {quantity_needed})")
                
                # Analyze how to obtain this material
                material_chain = material.get('chain', {})
                self._resolve_material_shortage(material_code, shortage, material_chain, actions, knowledge_base, map_state, client)
            else:
                self.logger.info(f"✅ Have sufficient {material_code} ({current_quantity}/{quantity_needed})")
        
        # Finally, add the crafting action for the target item
        workshop_type = chain_analysis.get('workshop_type')
        if workshop_type:
            self._add_crafting_sequence(target_item, workshop_type, actions, knowledge_base, client)
        
        return actions

    def _resolve_material_shortage(self, material_code: str, shortage: int, material_chain: Dict, actions: List[Dict], knowledge_base, map_state, client=None) -> None:
        """
        Resolve a shortage of a specific material by analyzing its source and adding appropriate actions.
        """
        chain_type = material_chain.get('type')
        
        if chain_type == 'base_resource':
            # Direct gathering: find → move → gather
            self.logger.info(f"🌿 {material_code} is a base resource - adding gathering actions")
            self._add_resource_gathering_sequence(material_code, shortage, actions)
            
        elif chain_type == 'transformable_resource':
            # Workshop transformation: need raw materials → find workshop → transform
            self.logger.info(f"🔨 {material_code} is transformable - analyzing raw material needs")
            raw_material = material_chain.get('raw_material')
            
            if raw_material:
                # Calculate raw material needed using API data
                transformation_ratio = self._get_transformation_ratio(raw_material, material_code, knowledge_base)
                raw_needed = shortage * transformation_ratio
                
                # Check if we have enough raw materials
                raw_current = self.character_inventory.get(raw_material, 0)
                raw_shortage = max(0, raw_needed - raw_current)
                
                if raw_shortage > 0:
                    self.logger.info(f"⛏️ Need {raw_shortage} {raw_material} to make {shortage} {material_code}")
                    self._add_resource_gathering_sequence(raw_material, raw_shortage, actions)
                
                # Add transformation sequence: find workshop → move → transform
                workshop_type = material_chain.get('workshop_type', 'mining')
                self._add_transformation_sequence(raw_material, material_code, workshop_type, shortage, actions)
            
        elif chain_type == 'craftable':
            # Recursive crafting - analyze the sub-recipe
            self.logger.info(f"🏭 {material_code} is craftable - analyzing sub-recipe")
            sub_required = material_chain.get('required_materials', [])
            
            # Recursively resolve each sub-material
            for sub_material in sub_required:
                sub_code = sub_material['material_code']
                sub_quantity_per_item = sub_material['quantity_required']
                sub_total_needed = sub_quantity_per_item * shortage
                
                sub_current = self.character_inventory.get(sub_code, 0)
                sub_shortage = max(0, sub_total_needed - sub_current)
                
                if sub_shortage > 0:
                    sub_chain = sub_material.get('chain', {})
                    self._resolve_material_shortage(sub_code, sub_shortage, sub_chain, actions, knowledge_base, map_state, client)
            
            # Add crafting for the intermediate item
            sub_workshop_type = material_chain.get('workshop_type')
            if sub_workshop_type:
                self._add_crafting_sequence(material_code, sub_workshop_type, actions, knowledge_base, client)

    def _add_resource_gathering_sequence(self, resource_code: str, quantity_needed: int, actions: List[Dict]) -> None:
        """Add find → move → gather sequence for a base resource."""
        actions.append({
            'name': 'find_resources',
            'params': {'resource_type': resource_code, 'quantity_needed': quantity_needed},
            'description': f"Find {resource_code} resource nodes (need {quantity_needed})"
        })
        actions.append({
            'name': 'move',
            'params': {'use_target_coordinates': True},
            'description': f"Move to {resource_code} resource location"
        })
        actions.append({
            'name': 'gather_resources',
            'params': {'resource_type': resource_code, 'quantity_needed': quantity_needed},
            'description': f"Gather {quantity_needed} {resource_code}"
        })

    def _add_transformation_sequence(self, raw_material: str, refined_material: str, workshop_type: str, quantity_needed: int, actions: List[Dict]) -> None:
        """Add find workshop → move → transform sequence."""
        actions.append({
            'name': 'find_correct_workshop',
            'params': {'workshop_type': workshop_type},
            'description': f"Find {workshop_type} workshop for transformation"
        })
        actions.append({
            'name': 'move',
            'params': {'use_target_coordinates': True},
            'description': f"Move to {workshop_type} workshop"
        })
        actions.append({
            'name': 'transform_raw_materials',
            'params': {'raw_material': raw_material, 'target_material': refined_material, 'quantity_needed': quantity_needed},
            'description': f"Transform {raw_material} to {quantity_needed} {refined_material}"
        })

    def _add_crafting_sequence(self, item_code: str, workshop_type: str, actions: List[Dict], knowledge_base=None, client=None) -> None:
        """Add find workshop → move → unequip (if needed) → craft → equip sequence."""
        actions.append({
            'name': 'find_correct_workshop',
            'params': {'workshop_type': workshop_type, 'item_code': item_code},
            'description': f"Find {workshop_type} workshop for crafting {item_code}"
        })
        actions.append({
            'name': 'move',
            'params': {'use_target_coordinates': True},
            'description': f"Move to {workshop_type} workshop"
        })
        
        # Check if we need to unequip any materials that are required for crafting
        equipped_materials = self._get_equipped_materials_for_item(item_code, knowledge_base, client)
        for material_code, slot in equipped_materials:
            actions.append({
                'name': 'unequip_item',
                'params': {'slot': slot},
                'description': f"Unequip {material_code} from {slot} for crafting"
            })
        
        actions.append({
            'name': 'craft_item',
            'params': {'item_code': item_code},
            'description': f"Craft {item_code}"
        })
        
        # Add equip action for weapons and armor
        equipment_slot = self._get_equipment_slot(item_code, workshop_type, knowledge_base, client)
        if equipment_slot:
            actions.append({
                'name': 'equip_item',
                'params': {'item_code': item_code, 'slot': equipment_slot},
                'description': f"Equip {item_code}"
            })

    def _get_transformation_ratio(self, raw_material: str, refined_material: str, knowledge_base) -> int:
        """Get the transformation ratio from API data by looking up the refined material's recipe."""
        # Check if we have knowledge base data for the refined material
        if knowledge_base and hasattr(knowledge_base, 'data'):
            items = knowledge_base.data.get('items', {})
            if refined_material in items:
                item_info = items[refined_material]
                craft_data = item_info.get('craft_data', {})
                items_required = craft_data.get('items', [])
                
                # Find the raw material in the recipe
                for item in items_required:
                    if item.get('code') == raw_material:
                        ratio = item.get('quantity', 1)
                        self.logger.info(f"📊 Found transformation ratio from API: {ratio} {raw_material} → 1 {refined_material}")
                        return ratio
        
        # Fallback: assume 1:1 ratio if no data available
        self.logger.warning(f"⚠️ No transformation ratio found for {raw_material} → {refined_material}, assuming 1:1")
        return 1

    def _add_gathering_actions(self, chain: Dict, actions: List[Dict], knowledge_base, map_state, total_materials: Dict[str, int] = None, visited: Set[str] = None) -> None:
        """
        Add resource gathering actions to the action sequence.
        """
        if visited is None:
            visited = set()
            
        item_code = chain.get('item_code')
        if item_code in visited:
            return
        visited.add(item_code)
        
        chain_type = chain.get('type')
        
        if chain_type == 'base_resource':
            # Check if we already have enough of this resource
            required_quantity = total_materials.get(item_code, 1) if total_materials else 1
            if self._has_sufficient_resources(item_code, required_quantity):
                self.logger.info(f"✅ Already have sufficient {item_code} in inventory - skipping gathering")
                return
                
            # Add resource gathering action sequence: find → move → gather
            actions.append({
                'name': 'find_resources',
                'params': {'resource_type': item_code},
                'description': f"Find {item_code} resource nodes"
            })
            actions.append({
                'name': 'move',
                'params': {'use_target_coordinates': True},  # Signal to use coordinates from context
                'description': f"Move to {item_code} resource location"
            })
            actions.append({
                'name': 'gather_resources',
                'params': {'resource_type': item_code},
                'description': f"Gather {item_code}"
            })
        elif chain_type == 'transformable_resource':
            # Check if we already have the refined material
            required_quantity = total_materials.get(item_code, 1) if total_materials else 1
            if self._has_sufficient_resources(item_code, required_quantity):
                self.logger.info(f"✅ Already have sufficient {item_code} in inventory - skipping transformation")
                return
                
            # First gather the raw material: find → move → gather → find workshop → move to workshop → transform
            raw_material = chain.get('raw_material')
            if raw_material:
                # Only gather raw material if we don't have enough
                raw_required_quantity = total_materials.get(raw_material, 1) if total_materials else 1
                if not self._has_sufficient_resources(raw_material, raw_required_quantity):
                    actions.append({
                        'name': 'find_resources',
                        'params': {'resource_type': raw_material},
                        'description': f"Find {raw_material} resource nodes"
                    })
                    actions.append({
                        'name': 'move',
                        'params': {'use_target_coordinates': True},
                        'description': f"Move to {raw_material} resource location"
                    })
                    actions.append({
                        'name': 'gather_resources',
                        'params': {'resource_type': raw_material},
                        'description': f"Gather {raw_material}"
                    })
                
                # Then transform it
                workshop_type = chain.get('workshop_type')
                actions.append({
                    'name': 'find_correct_workshop',
                    'params': {'workshop_type': workshop_type},
                    'description': f"Find {workshop_type} workshop"
                })
                actions.append({
                    'name': 'move',
                    'params': {'use_target_coordinates': True},
                    'description': f"Move to {workshop_type} workshop"
                })
                actions.append({
                    'name': 'transform_raw_materials',
                    'params': {'raw_material': raw_material, 'target_material': item_code},
                    'description': f"Transform {raw_material} to {item_code}"
                })
        elif chain_type == 'craftable':
            # Recursively add gathering for all required materials
            for material in chain.get('required_materials', []):
                material_chain = material.get('chain')
                if material_chain:
                    self._add_gathering_actions(material_chain, actions, knowledge_base, map_state, total_materials, visited)

    def _add_crafting_actions(self, chain: Dict, actions: List[Dict], knowledge_base) -> None:
        """
        Add crafting actions to the action sequence.
        """
        chain_type = chain.get('type')
        
        if chain_type == 'craftable':
            # First add crafting for all dependencies
            for material in chain.get('required_materials', []):
                material_chain = material.get('chain')
                if material_chain and material_chain.get('type') == 'craftable':
                    self._add_crafting_actions(material_chain, actions, knowledge_base)
            
            # Then add crafting for this item: find workshop → move to workshop → craft → equip
            workshop_type = chain.get('workshop_type')
            item_code = chain.get('item_code')
            
            actions.append({
                'name': 'find_correct_workshop',
                'params': {'workshop_type': workshop_type, 'item_code': item_code},
                'description': f"Find {workshop_type} workshop for {item_code}"
            })
            # Use check_location to establish spatial context instead of move
            actions.append({
                'name': 'check_location',
                'params': {},
                'description': "Check location and establish spatial context for crafting"
            })
            # Add material transformation step (copper_ore -> copper)
            actions.append({
                'name': 'transform_raw_materials',
                'params': {'target_item': item_code},
                'description': f"Transform raw materials for {item_code}"
            })
            actions.append({
                'name': 'craft_item',
                'params': {'item_code': item_code},
                'description': f"Craft {item_code}"
            })
            # Add equip action for weapons and armor
            equipment_slot = self._get_equipment_slot(item_code, workshop_type, knowledge_base, client)
            if equipment_slot:
                actions.append({
                    'name': 'equip_item',
                    'params': {'item_code': item_code, 'slot': equipment_slot},
                    'description': f"Equip {item_code}"
                })

    def _extract_raw_materials(self, chain_analysis: Dict) -> List[str]:
        """
        Extract all raw materials needed for the crafting chain.
        """
        raw_materials = []
        
        def extract_from_chain(chain):
            chain_type = chain.get('type')
            if chain_type == 'base_resource':
                raw_materials.append(chain.get('item_code'))
            elif chain_type == 'transformable_resource':
                raw_material = chain.get('raw_material')
                if raw_material:
                    raw_materials.append(raw_material)
            elif chain_type == 'craftable':
                for material in chain.get('required_materials', []):
                    material_chain = material.get('chain')
                    if material_chain:
                        extract_from_chain(material_chain)
        
        extract_from_chain(chain_analysis)
        return list(set(raw_materials))  # Remove duplicates

    def _get_item_from_knowledge(self, item_code: str, knowledge_base) -> Optional[Dict]:
        """
        Get item data from knowledge base if available.
        
        Returns item data as a dictionary, or None if not found.
        """
        if not knowledge_base or not hasattr(knowledge_base, 'data'):
            return None
        
        items = knowledge_base.data.get('items', {})
        if item_code not in items:
            return None
        
        return items[item_code]

    def _get_character_inventory(self, client) -> Dict[str, int]:
        """
        Get character inventory from knowledge base/character state.
        """
        try:
            # Use ActionContext to get inventory
            from src.lib.action_context import ActionContext
            
            # Get controller from kwargs if available
            controller = self.kwargs.get('controller')
            if controller:
                context = ActionContext.from_controller(controller)
                return context.get_character_inventory()
            
            # Fallback to character state if available
            character_state = self.kwargs.get('character_state')
            if character_state and hasattr(character_state, 'data'):
                inventory_dict = {}
                char_data = character_state.data
                
                # Get inventory items
                inventory_items = char_data.get('inventory', [])
                for item in inventory_items:
                    if isinstance(item, dict):
                        code = item.get('code')
                        quantity = item.get('quantity', 0)
                        if code and quantity > 0:
                            inventory_dict[code] = quantity
                
                # Include equipped items dynamically
                for key, value in char_data.items():
                    if isinstance(value, str) and value:
                        # This might be an equipped item
                        if value not in inventory_dict and key not in ['name', 'skin', 'account']:
                            inventory_dict[value] = inventory_dict.get(value, 0) + 1
                            self.logger.debug(f"Including equipped item {value} from {key} as available material")
                
                return inventory_dict
            
            return {}
            
        except Exception as e:
            self.logger.warning(f"Could not get character inventory: {e}")
            return {}

    def _has_sufficient_resources(self, item_code: str, required_quantity: int = 1) -> bool:
        """
        Check if character has sufficient resources in inventory.
        
        Args:
            item_code: Item to check for
            required_quantity: Minimum quantity needed (should come from recipe data)
        """
        if not hasattr(self, 'character_inventory'):
            return False
        
        current_quantity = self.character_inventory.get(item_code, 0)
        has_enough = current_quantity >= required_quantity
        
        if has_enough:
            self.logger.info(f"✅ Have {current_quantity} {item_code} (need {required_quantity}) - sufficient!")
        else:
            self.logger.info(f"❌ Have {current_quantity} {item_code} (need {required_quantity}) - need more")
            
        return has_enough

    def _get_equipped_materials_for_item(self, item_code: str, knowledge_base, client) -> List[Tuple[str, str]]:
        """
        Check which required materials for an item are currently equipped.
        
        Returns:
            List of tuples (material_code, slot_name) for materials that need to be unequipped
        """
        equipped_materials = []
        
        if not knowledge_base or not hasattr(knowledge_base, 'data'):
            return equipped_materials
            
        # Get the item's craft data to find required materials
        items = knowledge_base.data.get('items', {})
        if item_code not in items:
            return equipped_materials
            
        item_data = items[item_code]
        craft_data = item_data.get('craft_data', {})
        if not craft_data:
            return equipped_materials
            
        required_materials = craft_data.get('items', [])
        
        # Get character data from context if available
        try:
            # This method is called during chain analysis, need to pass context through
            context = getattr(self, 'current_context', None)
            if context and hasattr(context, 'character_state'):
                character_state = context.character_state
            else:
                return equipped_materials
            
            if character_state and hasattr(character_state, 'data'):
                char_data = character_state.data
                
                # Dynamically check all keys for equipped items
                for key, value in char_data.items():
                    # If this is a string value that matches a required material
                    if isinstance(value, str) and value:
                        for material in required_materials:
                            if material.get('code') == value:
                                # Use the key directly as the slot name
                                equipped_materials.append((value, key))
                                self.logger.info(f"Material {value} is equipped in {key}, will need to unequip")
                                break
        except Exception as e:
            self.logger.warning(f"Could not check equipped materials: {e}")
            
        return equipped_materials

    def __repr__(self):
        return "AnalyzeCraftingChainAction()"
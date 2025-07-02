""" TransformRawMaterialsAction module """

import time
from typing import Dict, Optional

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api
from artifactsmmo_api_client.api.items.get_item_items_code_get import sync as get_item_api
from artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post import sync as crafting_api
from artifactsmmo_api_client.models.crafting_schema import CraftingSchema

from src.lib.action_context import ActionContext

from .base import ActionBase
from .check_inventory import CheckInventoryAction
from .move import MoveAction


class TransformRawMaterialsAction(ActionBase):
    """ Action to transform raw materials into refined materials (e.g., copper_ore → copper) """

    # GOAP parameters
    conditions = {
            'character_status': {
                'alive': True,
                'safe': True,
            },
            'inventory_status': {
                'has_raw_materials': True
            }
        }
    reactions = {
        'inventory_status': {
            'has_refined_materials': True,
            'materials_sufficient': True
        }
    }
    weights = {"inventory_status.has_refined_materials": 15}

    def __init__(self):
        """
        Initialize the transform raw materials action.
        """
        super().__init__()

    def execute(self, client, context: ActionContext) -> Optional[Dict]:
        """ Transform raw materials into refined materials needed for crafting """
        # Get parameters from context
        character_name = context.character_name
        target_item = context.get('target_item')
        
        # Store context for use by helper methods
        self._context = context
        
        self.log_execution_start(character_name=character_name, target_item=target_item)
        
        try:
            # Get current character data to check inventory
            character_response = get_character_api(name=character_name, client=client)
            
            if not character_response or not character_response.data:
                error_response = self.get_error_response('Could not get character data')
                self.log_execution_result(error_response)
                return error_response
                
            character_data = character_response.data
            character_x = character_data.x
            character_y = character_data.y
            inventory = character_data.inventory or []
            
            # Get the actual requirements for the target item first
            required_materials_dict = {}
            if target_item:
                required_materials_dict = self._get_required_materials_for_item(client, target_item)
                self.logger.info(f"🔍 Required materials for {target_item}: {required_materials_dict}")
            
            # Determine what raw materials to transform based on target item and inventory
            materials_to_transform = self._determine_materials_to_transform(client, inventory, target_item, required_materials_dict)
            
            if not materials_to_transform:
                error_response = self.get_error_response('No raw materials found that need transformation')
                self.log_execution_result(error_response)
                return error_response
            
            self.logger.info(f"🔄 Transforming materials: {materials_to_transform}")
            
            results = []
            for raw_material, refined_material, quantity in materials_to_transform:
                self.logger.info(f"🔄 Transforming {quantity}x {raw_material} → {refined_material}")
                
                # First ensure we're at the correct workshop for this transformation
                required_workshop = self._get_required_workshop_for_material(raw_material, refined_material, client)
                if required_workshop:
                    move_result = self._move_to_correct_workshop(client, required_workshop, character_name, context)
                    if not move_result:
                        self.logger.error(f"❌ Could not move to {required_workshop} workshop for {raw_material} transformation")
                        results.append({
                            'raw_material': raw_material,
                            'refined_material': refined_material,
                            'quantity': quantity,
                            'success': False,
                            'error': f"Could not find {required_workshop} workshop"
                        })
                        continue
                
                # Check for cooldown after movement and wait if needed
                character_check = get_character_api(name=character_name, client=client)
                if character_check and character_check.data and character_check.data.cooldown > 0:
                    cooldown_seconds = character_check.data.cooldown
                    self.logger.info(f"⏳ Cooldown active after movement: {cooldown_seconds} seconds - waiting...")
                    # Wait for cooldown to expire
                    # Get cooldown buffer from configuration
                    action_config = context.get('action_config', {})
                    cooldown_buffer = action_config.get('cooldown_buffer_seconds', 1)
                    time.sleep(cooldown_seconds + cooldown_buffer)
                    self.logger.info(f"✅ Waited {cooldown_seconds} seconds for cooldown - proceeding with crafting")
                
                # Use crafting API to smelt/refine the material
                # For smelting, we need to find the recipe that produces the refined material
                recipe_code = self._find_smelting_recipe(client, raw_material, refined_material)
                if not recipe_code:
                    self.logger.error(f"❌ Could not find smelting recipe for {raw_material} → {refined_material}")
                    results.append({
                        'raw_material': raw_material,
                        'refined_material': refined_material,
                        'quantity': quantity,
                        'success': False,
                        'error': f"No smelting recipe found for {raw_material} → {refined_material}"
                    })
                    continue
                
                self.logger.info(f"🔥 Using recipe '{recipe_code}' to smelt {raw_material} → {refined_material}")
                crafting_schema = CraftingSchema(code=recipe_code, quantity=quantity)
                craft_response = crafting_api(name=character_name, client=client, body=crafting_schema)
                
                if craft_response and hasattr(craft_response, 'data') and craft_response.data:
                    craft_data = craft_response.data
                    self.logger.info(f"✅ Crafting completed for {refined_material}")
                    
                    # Use check_inventory action to verify the smelted material is now in inventory
                    check_inventory_action = CheckInventoryAction()
                    # Create a temporary context for check_inventory
                    check_context = ActionContext()
                    check_context.update(context)
                    check_context['required_items'] = [refined_material]
                    inventory_result = check_inventory_action.execute(client, check_context)
                    
                    if inventory_result and inventory_result.get('success') and inventory_result.get('inventory_status'):
                        inventory_status = inventory_result['inventory_status']
                        if refined_material in inventory_status and inventory_status[refined_material]['available'] > 0:
                            refined_count = inventory_status[refined_material]['available']
                            self.logger.info(f"✅ Verified: {refined_count}x {refined_material} now in inventory")
                            results.append({
                                'raw_material': raw_material,
                                'refined_material': refined_material,
                                'quantity': quantity,
                                'success': True,
                                'verified_quantity': refined_count,
                                'craft_data': craft_data
                            })
                        else:
                            self.logger.warning(f"⚠️ Crafting completed but {refined_material} not found in inventory")
                            results.append({
                                'raw_material': raw_material,
                                'refined_material': refined_material,
                                'quantity': quantity,
                                'success': False,
                                'error': f"Smelted {refined_material} not found in inventory after crafting"
                            })
                    else:
                        self.logger.error(f"❌ Could not verify inventory after smelting {refined_material}")
                        results.append({
                            'raw_material': raw_material,
                            'refined_material': refined_material,
                            'quantity': quantity,
                            'success': False,
                            'error': f"Could not verify {refined_material} in inventory after smelting"
                        })
                else:
                    self.logger.error(f"❌ Failed to craft {refined_material} from {raw_material}")
                    results.append({
                        'raw_material': raw_material,
                        'refined_material': refined_material,
                        'quantity': quantity,
                        'success': False,
                        'error': f"Crafting failed for {refined_material}"
                    })
            
            # Check if any transformations were successful
            successful_transforms = [r for r in results if r['success']]
            if successful_transforms:
                result = {
                    'success': True,
                    'materials_transformed': successful_transforms,
                    'total_transformations': len(successful_transforms),
                    'target_item': target_item,
                    'character_x': character_x,
                    'character_y': character_y
                }
                self.log_execution_result(result)
                return result
            else:
                error_response = self.get_error_response(f'All material transformations failed: {results}')
                self.log_execution_result(error_response)
                return error_response
                
        except Exception as e:
            error_response = self.get_error_response(f"Material transformation failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def _determine_materials_to_transform(self, client, inventory: list, target_item: str, required_materials: dict) -> list:
        """
        Determine which raw materials need to be transformed based on target item requirements.
        
        Args:
            client: API client
            inventory: Character inventory
            target_item: Final item to be crafted
            
        Returns:
            List of tuples: (raw_material, refined_material, quantity)
        """
        # Create inventory lookup
        inventory_dict = {}
        for item in inventory:
            # Handle both dict and InventorySlot object formats
            if hasattr(item, 'code') and hasattr(item, 'quantity'):
                # InventorySlot object format
                code = item.code
                quantity = item.quantity
            elif isinstance(item, dict):
                # Dict format  
                code = item.get('code')
                quantity = item.get('quantity', 0)
            else:
                continue
                
            if code and quantity > 0:
                inventory_dict[code] = quantity
        
        # Get material transformations from knowledge base or API
        material_transforms = self._get_material_transformations_from_knowledge_base(client)
        
        # Check if we can craft directly without transformation (fallback)
        if required_materials:
            for raw_material in required_materials:
                if raw_material in inventory_dict and raw_material in material_transforms.values():
                    # Skip transformation if we already have the refined material
                    self.logger.info(f"✅ Already have required material {raw_material} in inventory")
                    continue
        
        # If we have a target item, try to determine required materials for transformation planning
        target_required_materials_dict = {}
        if target_item:
            target_required_materials_dict = self._get_required_materials_for_item(client, target_item)
        
        # Determine transformations based on what we have and what we need
        transformations = []
        
        for raw_material, refined_material in material_transforms.items():
            raw_quantity = inventory_dict.get(raw_material, 0)
            refined_quantity = inventory_dict.get(refined_material, 0)
            
            if raw_quantity > 0:
                # Check if we need this refined material for our target
                if target_required_materials_dict and refined_material in target_required_materials_dict:
                    needed_quantity = target_required_materials_dict[refined_material]
                    
                    # Only transform if we don't have enough refined material
                    if refined_quantity < needed_quantity:
                        # Get the exact recipe requirements from API
                        recipe_requirements = self._get_recipe_requirements(client, refined_material)
                        if recipe_requirements and raw_material in recipe_requirements:
                            raw_needed_per_craft = recipe_requirements[raw_material]
                            # Calculate how many units we can actually craft
                            max_craftable = raw_quantity // raw_needed_per_craft
                            if max_craftable > 0:
                                transformations.append((raw_material, refined_material, max_craftable))
                        else:
                            self.logger.warning(f"⚠️ Could not determine recipe requirements for {refined_material}")
                elif not target_required_materials_dict:
                    # If we don't know requirements, use API recipe data to determine how much we can craft
                    recipe_requirements = self._get_recipe_requirements(client, refined_material)
                    if recipe_requirements and raw_material in recipe_requirements:
                        raw_needed_per_craft = recipe_requirements[raw_material]
                        # Calculate how many units we can actually craft
                        max_craftable = raw_quantity // raw_needed_per_craft
                        if max_craftable > 0:
                            # Get default craft quantity from configuration
                            action_config = self._context.get('action_config', {})
                            default_craft_quantity = action_config.get('default_transform_quantity', 1)
                            craft_quantity = min(max_craftable, default_craft_quantity)
                            transformations.append((raw_material, refined_material, craft_quantity))
                    else:
                        self.logger.warning(f"⚠️ Could not determine recipe requirements for {refined_material}")
        
        return transformations

    def _get_recipe_requirements(self, client, refined_material: str) -> dict:
        """
        Get the exact recipe requirements for a refined material from the API.
        
        Args:
            client: API client
            refined_material: The refined material to get recipe for (e.g., 'copper')
            
        Returns:
            Dict mapping raw material code to required quantity per craft
        """
        try:
            
            item_response = get_item_api(code=refined_material, client=client)
            if item_response and item_response.data and hasattr(item_response.data, 'craft'):
                craft_data = item_response.data.craft
                if hasattr(craft_data, 'items') and craft_data.items:
                    requirements = {}
                    for item in craft_data.items:
                        if hasattr(item, 'code') and hasattr(item, 'quantity'):
                            requirements[item.code] = item.quantity
                    self.logger.info(f"📋 Recipe for {refined_material}: {requirements}")
                    return requirements
            
            self.logger.warning(f"⚠️ No recipe data found for {refined_material}")
            return {}
            
        except Exception as e:
            self.logger.error(f"Error getting recipe requirements for {refined_material}: {e}")
            return {}

    def _get_required_materials_for_item(self, client, item_code: str) -> dict:
        """
        Get the required materials for crafting an item.
        
        Args:
            client: API client
            item_code: Item to check requirements for
            
        Returns:
            Dict mapping material code to required quantity
        """
        try:
            item_response = get_item_api(code=item_code, client=client)
            if not item_response or not item_response.data:
                return {}
            
            item_data = item_response.data
            if not hasattr(item_data, 'craft') or not item_data.craft:
                return {}
            
            craft_data = item_data.craft
            required_materials = {}
            
            if hasattr(craft_data, 'items') and craft_data.items:
                for item in craft_data.items:
                    if hasattr(item, 'code') and hasattr(item, 'quantity'):
                        required_materials[item.code] = item.quantity
            
            return required_materials
            
        except Exception as e:
            self.logger.warning(f"Could not determine required materials for {item_code}: {e}")
            return {}

    def _get_required_workshop_for_material(self, raw_material: str, refined_material: str, client) -> Optional[str]:
        """
        Get the workshop type required for transforming a raw material by checking API.
        
        Args:
            raw_material: Raw material code (e.g., 'copper_ore')
            refined_material: Refined material code (e.g., 'copper')
            client: API client for looking up item recipes
            
        Returns:
            Workshop type required for transformation
        """
        try:
            # Look up the refined material in the API to see what workshop it requires
            
            item_response = get_item_api(code=refined_material, client=client)
            if item_response and item_response.data and hasattr(item_response.data, 'craft'):
                craft_data = item_response.data.craft
                if hasattr(craft_data, 'skill'):
                    skill_required = craft_data.skill
                    self.logger.info(f"🔍 API indicates {refined_material} requires {skill_required} skill")
                    
                    # Get skill to workshop mapping from knowledge base or config
                    workshop_type = self._get_workshop_for_skill(skill_required)
                    if workshop_type:
                        self.logger.info(f"✅ Determined {raw_material} → {refined_material} requires {workshop_type} workshop")
                        return workshop_type
                    else:
                        self.logger.error(f"❌ Unknown skill '{skill_required}' for {refined_material} - cannot determine workshop")
                        return None
            
            # If API lookup fails or no craft data available, cannot determine workshop
            self.logger.error(f"❌ Could not determine workshop from API for {refined_material} - no craft data available")
            return None
            
        except Exception as e:
            self.logger.error(f"Error determining workshop for {raw_material}: {e}")
            return None

    def _move_to_correct_workshop(self, client, workshop_type: str, character_name: str, context: ActionContext) -> bool:
        """
        Move to the correct workshop for material transformation.
        
        Args:
            client: API client
            workshop_type: Type of workshop needed (e.g., 'mining')
            character_name: Name of the character
            context: ActionContext containing knowledge_base and map_state
            
        Returns:
            True if successfully moved to correct workshop, False otherwise
        """
        try:
            # Get knowledge base and map state from context
            knowledge_base = context.knowledge_base
            map_state = context.map_state
            
            # Search for the workshop in knowledge base first
            workshop_location = self._find_workshop_in_knowledge_base(knowledge_base, workshop_type)
            
            if workshop_location:
                x, y = workshop_location
                self.logger.info(f"🏭 Found {workshop_type} workshop at ({x}, {y}) in knowledge base")
                
                # Check if character is already at the workshop
                character_response = get_character_api(name=character_name, client=client)
                if character_response and character_response.data:
                    current_x = character_response.data.x
                    current_y = character_response.data.y
                    
                    if current_x == x and current_y == y:
                        self.logger.info(f"✅ Already at {workshop_type} workshop at ({x}, {y}) - no movement needed")
                        return True
                
                # Move to the workshop
                move_action = MoveAction()
                
                move_context = ActionContext(
                    character_name=character_name,
                    action_data={'x': x, 'y': y},
                    knowledge_base=context.knowledge_base,
                    map_state=context.map_state
                )
                
                move_result = move_action.execute(client, move_context)
                
                # Handle both successful move and "already at destination" error
                if move_result and (
                    (hasattr(move_result, 'data') and move_result.data) or
                    (isinstance(move_result, dict) and move_result.get('success'))
                ):
                    self.logger.info(f"✅ Successfully moved to {workshop_type} workshop at ({x}, {y})")
                    return True
                elif isinstance(move_result, dict) and 'already at destination' in str(move_result.get('error', '')).lower():
                    self.logger.info(f"✅ Already at {workshop_type} workshop at ({x}, {y})")
                    return True
                else:
                    self.logger.error(f"❌ Failed to move to {workshop_type} workshop at ({x}, {y}): {move_result}")
                    return False
            else:
                self.logger.error(f"❌ Could not find {workshop_type} workshop in knowledge base")
                return False
                
        except Exception as e:
            self.logger.error(f"Error moving to {workshop_type} workshop: {e}")
            return False

    def _find_workshop_in_knowledge_base(self, knowledge_base, workshop_type: str) -> Optional[tuple]:
        """
        Find a workshop location in the knowledge base.
        
        Args:
            knowledge_base: KnowledgeBase instance
            workshop_type: Type of workshop to find
            
        Returns:
            (x, y) tuple if found, None otherwise
        """
        if not knowledge_base or not hasattr(knowledge_base, 'data'):
            return None
            
        workshops = knowledge_base.data.get('workshops', {})
        for workshop_code, workshop_data in workshops.items():
            if workshop_type.lower() in workshop_code.lower():
                x = workshop_data.get('x')
                y = workshop_data.get('y')
                if x is not None and y is not None:
                    return (x, y)
        
        return None

    def _find_smelting_recipe(self, client, raw_material: str, refined_material: str) -> Optional[str]:
        """
        Find the recipe code that smelts raw_material into refined_material.
        
        Args:
            client: API client
            raw_material: Raw material code (e.g., 'copper_ore')
            refined_material: Refined material code (e.g., 'copper')
            
        Returns:
            Recipe code that produces the refined material, or the refined material itself if direct crafting
        """
        try:
            # For common smelting patterns, the refined material itself is often the recipe
            # Let's first try the refined material as the recipe code
            
            item_response = get_item_api(code=refined_material, client=client)
            if item_response and item_response.data:
                item_data = item_response.data
                # Check if this item can be crafted
                if hasattr(item_data, 'craft') and item_data.craft:
                    craft_info = item_data.craft
                    self.logger.info(f"📋 Found craft info for {refined_material}: skill={getattr(craft_info, 'skill', 'unknown')}")
                    
                    # Check if the required materials match our raw material
                    if hasattr(craft_info, 'items') and craft_info.items:
                        required_materials = []
                        for item in craft_info.items:
                            if hasattr(item, 'code'):
                                required_materials.append(item.code)
                        
                        if raw_material in required_materials:
                            self.logger.info(f"✅ Recipe '{refined_material}' uses {raw_material} as input")
                            return refined_material
                        else:
                            self.logger.warning(f"❌ Recipe '{refined_material}' doesn't use {raw_material} (uses: {required_materials})")

            self.logger.error(f"❌ No smelting recipe found for {raw_material} → {refined_material}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding smelting recipe for {raw_material} → {refined_material}: {e}")
            return None

    def _get_material_transformations_from_knowledge_base(self, client) -> dict:
        """
        Get material transformation mappings from knowledge base or API.
        
        Returns:
            Dict mapping raw material codes to refined material codes
        """
        transformations = {}
        
        # First try knowledge base
        knowledge_base = self._context.knowledge_base
        if knowledge_base and hasattr(knowledge_base, 'data'):
            items = knowledge_base.data.get('items', {})
            
            # Look for items that can be crafted from raw materials
            for item_code, item_data in items.items():
                craft_data = item_data.get('craft_data', {})
                if craft_data and 'items' in craft_data:
                    # Check if this is a material transformation (1 input -> 1 output)
                    craft_items = craft_data.get('items', [])
                    if len(craft_items) == 1:
                        input_item = craft_items[0]
                        if isinstance(input_item, dict):
                            raw_material = input_item.get('code')
                            if raw_material and self._is_raw_material(raw_material):
                                transformations[raw_material] = item_code
                                self.logger.debug(f"Found transformation: {raw_material} → {item_code}")
        
        # If no transformations found in knowledge base, try API discovery
        if not transformations:
            # Get common raw materials from configuration
            action_config = self._context.get('action_config', {})
            raw_material_patterns = action_config.get('raw_material_patterns', ['_ore', '_wood'])
            
            # Check a sample of items to discover transformations
            sample_items = action_config.get('transformation_sample_items', [])
            
            for item_code in sample_items:
                try:
                    item_response = get_item_api(code=item_code, client=client)
                    if item_response and item_response.data:
                        item_data = item_response.data
                        if hasattr(item_data, 'craft') and item_data.craft:
                            craft_info = item_data.craft
                            if hasattr(craft_info, 'items') and craft_info.items:
                                # Check if this is a simple transformation
                                if len(craft_info.items) == 1:
                                    input_item = craft_info.items[0]
                                    if hasattr(input_item, 'code'):
                                        raw_material = input_item.code
                                        if any(pattern in raw_material for pattern in raw_material_patterns):
                                            transformations[raw_material] = item_code
                                            self.logger.debug(f"Discovered transformation: {raw_material} → {item_code}")
                except Exception as e:
                    self.logger.debug(f"Could not check {item_code}: {e}")
        
        self.logger.info(f"Loaded {len(transformations)} material transformations")
        return transformations
    
    def _is_raw_material(self, material_code: str) -> bool:
        """
        Check if a material is a raw material based on naming patterns or knowledge base.
        """
        # Get raw material patterns from configuration
        action_config = self._context.get('action_config', {})
        raw_patterns = action_config.get('raw_material_patterns', ['_ore', '_wood'])
        
        # Check if it matches any raw material pattern
        return any(pattern in material_code for pattern in raw_patterns)
    
    def _get_workshop_for_skill(self, skill: str) -> Optional[str]:
        """
        Get workshop type for a given skill from knowledge base or configuration.
        """
        # First check knowledge base for workshop skill mappings
        knowledge_base = self._context.knowledge_base
        if knowledge_base and hasattr(knowledge_base, 'data'):
            workshops = knowledge_base.data.get('workshops', {})
            for workshop_code, workshop_data in workshops.items():
                workshop_skill = workshop_data.get('skill')
                if workshop_skill == skill:
                    # Extract workshop type from code (e.g., 'mining_workshop_1' -> 'mining')
                    workshop_type = workshop_code.split('_')[0]
                    return workshop_type
        
        # Fallback to configuration mapping
        action_config = self._context.get('action_config', {})
        skill_workshop_mapping = action_config.get('skill_workshop_mapping', {})
        
        # If no mapping in config, use skill name as workshop type (common pattern)
        return skill_workshop_mapping.get(skill, skill)

    def __repr__(self):
        return "TransformRawMaterialsAction()"
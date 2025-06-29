""" TransformRawMaterialsAction module """

from typing import Dict, Optional
from artifactsmmo_api_client.api.my_characters.action_crafting_my_name import sync as crafting_api
from artifactsmmo_api_client.api.items.get_item import sync as get_item_api
from artifactsmmo_api_client.api.maps.get_map_x_y import sync as get_map_api
from artifactsmmo_api_client.models.crafting_schema import CraftingSchema
from .base import ActionBase


class TransformRawMaterialsAction(ActionBase):
    """ Action to transform raw materials into refined materials (e.g., copper_ore → copper) """

    # GOAP parameters
    conditions = {"character_alive": True, "has_raw_materials": True, "character_safe": True}
    reactions = {"has_refined_materials": True, "materials_sufficient": True}
    weights = {"has_refined_materials": 15}

    def __init__(self, character_name: str, target_item: str = None):
        """
        Initialize the transform raw materials action.

        Args:
            character_name: Name of the character performing the action
            target_item: Final item to be crafted (used to determine required materials)
        """
        super().__init__()
        self.character_name = character_name
        self.target_item = target_item

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """ Transform raw materials into refined materials needed for crafting """
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        self.log_execution_start(character_name=self.character_name, target_item=self.target_item)
        
        try:
            # Get current character data to check inventory
            from artifactsmmo_api_client.api.characters.get_character_name import sync as get_character_api
            character_response = get_character_api(name=self.character_name, client=client)
            
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
            if self.target_item:
                required_materials_dict = self._get_required_materials_for_item(client, self.target_item)
                self.logger.info(f"🔍 Required materials for {self.target_item}: {required_materials_dict}")
            
            # Determine what raw materials to transform based on target item and inventory
            materials_to_transform = self._determine_materials_to_transform(client, inventory, self.target_item, required_materials_dict)
            
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
                    move_result = self._move_to_correct_workshop(client, required_workshop, kwargs)
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
                import time
                from artifactsmmo_api_client.api.characters.get_character_name import sync as get_character_api
                character_check = get_character_api(name=self.character_name, client=client)
                if character_check and character_check.data and character_check.data.cooldown > 0:
                    cooldown_seconds = character_check.data.cooldown
                    self.logger.info(f"⏳ Cooldown active after movement: {cooldown_seconds} seconds - waiting...")
                    # Wait for cooldown to expire
                    time.sleep(cooldown_seconds + 1)  # Add 1 second buffer
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
                craft_response = crafting_api(name=self.character_name, client=client, body=crafting_schema)
                
                if craft_response and hasattr(craft_response, 'data') and craft_response.data:
                    craft_data = craft_response.data
                    self.logger.info(f"✅ Crafting completed for {refined_material}")
                    
                    # Use check_inventory action to verify the smelted material is now in inventory
                    from .check_inventory import CheckInventoryAction
                    check_inventory_action = CheckInventoryAction(self.character_name, required_items=[refined_material])
                    inventory_result = check_inventory_action.execute(client, **kwargs)
                    
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
                    'target_item': self.target_item,
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
        
        # Common material transformation mappings
        material_transforms = {
            'copper_ore': 'copper',
            'iron_ore': 'iron',
            'coal_ore': 'coal',
            'gold_ore': 'gold',
            'ash_wood': 'ash_plank',
            'birch_wood': 'birch_plank',
            'spruce_wood': 'spruce_plank',
            'dead_wood': 'hardwood_plank'
        }
        
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
                            # Limit to a reasonable amount when no target specified
                            craft_quantity = min(max_craftable, 1)  # Craft only 1 unit when no target
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
            from artifactsmmo_api_client.api.items.get_item import sync as get_item_api
            
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
            from artifactsmmo_api_client.api.items.get_item import sync as get_item_api
            
            item_response = get_item_api(code=refined_material, client=client)
            if item_response and item_response.data and hasattr(item_response.data, 'craft'):
                craft_data = item_response.data.craft
                if hasattr(craft_data, 'skill'):
                    skill_required = craft_data.skill
                    self.logger.info(f"🔍 API indicates {refined_material} requires {skill_required} skill")
                    
                    # Map skills to workshop types
                    skill_to_workshop = {
                        'weaponcrafting': 'weaponcrafting',
                        'gearcrafting': 'gearcrafting', 
                        'jewelrycrafting': 'jewelrycrafting',
                        'cooking': 'cooking',
                        'alchemy': 'alchemy',
                        'mining': 'mining',
                        'woodcutting': 'woodcutting'
                    }
                    
                    workshop_type = skill_to_workshop.get(skill_required)
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

    def _move_to_correct_workshop(self, client, workshop_type: str, kwargs: dict) -> bool:
        """
        Move to the correct workshop for material transformation.
        
        Args:
            client: API client
            workshop_type: Type of workshop needed (e.g., 'mining')
            kwargs: Context containing knowledge_base and map_state
            
        Returns:
            True if successfully moved to correct workshop, False otherwise
        """
        try:
            # Get knowledge base and map state from context
            knowledge_base = kwargs.get('knowledge_base')
            map_state = kwargs.get('map_state')
            
            # Search for the workshop in knowledge base first
            workshop_location = self._find_workshop_in_knowledge_base(knowledge_base, workshop_type)
            
            if workshop_location:
                x, y = workshop_location
                self.logger.info(f"🏭 Found {workshop_type} workshop at ({x}, {y}) in knowledge base")
                
                # Check if character is already at the workshop
                from artifactsmmo_api_client.api.characters.get_character_name import sync as get_character_api
                character_response = get_character_api(name=self.character_name, client=client)
                if character_response and character_response.data:
                    current_x = character_response.data.x
                    current_y = character_response.data.y
                    
                    if current_x == x and current_y == y:
                        self.logger.info(f"✅ Already at {workshop_type} workshop at ({x}, {y}) - no movement needed")
                        return True
                
                # Move to the workshop
                from .move import MoveAction
                move_action = MoveAction(self.character_name, x, y)
                move_result = move_action.execute(client)
                
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
            from artifactsmmo_api_client.api.items.get_item import sync as get_item_api
            
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

    def __repr__(self):
        return f"TransformRawMaterialsAction({self.character_name}, target={self.target_item})"
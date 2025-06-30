"""
Capability analyzer for examining resource drops, crafting recipes, and item stats.
Enables the player to understand upgrade chains like ash_tree → ash_wood → wooden_staff.
"""

from typing import Dict, List, Optional, Tuple
from artifactsmmo_api_client.api.resources.get_resource_resources_code_get import sync as get_resource_api
from artifactsmmo_api_client.api.items.get_item_items_code_get import sync as get_item_api
from artifactsmmo_api_client.models.resource_response_schema import ResourceResponseSchema
from artifactsmmo_api_client.models.item_response_schema import ItemResponseSchema
from artifactsmmo_api_client.types import UNSET
import logging

logger = logging.getLogger(__name__)


class CapabilityAnalyzer:
    """Analyzes capabilities of resources, items, and upgrade chains."""
    
    def __init__(self, client):
        self.client = client
        self._resource_cache: Dict[str, ResourceResponseSchema] = {}
        self._item_cache: Dict[str, ItemResponseSchema] = {}
    
    def analyze_resource_drops(self, resource_code: str) -> List[Dict]:
        """
        Analyze what items a resource drops.
        
        Args:
            resource_code: The resource code (e.g., "ash_tree")
            
        Returns:
            List of drop information with codes, rates, and quantities
        """
        try:
            if resource_code not in self._resource_cache:
                logger.info(f"🔍 Analyzing resource: {resource_code}")
                response = get_resource_api(client=self.client, code=resource_code)
                self._resource_cache[resource_code] = response
            
            resource = self._resource_cache[resource_code]
            drops = []
            
            for drop in resource.data.drops:
                drop_info = {
                    "item_code": drop.code,
                    "drop_rate": drop.rate,
                    "min_quantity": drop.min_quantity,
                    "max_quantity": drop.max_quantity,
                    "probability": f"1/{drop.rate}"
                }
                drops.append(drop_info)
                logger.info(f"  📦 Drops: {drop.code} (rate: 1/{drop.rate}, qty: {drop.min_quantity}-{drop.max_quantity})")
            
            return drops
            
        except Exception as e:
            logger.error(f"❌ Failed to analyze resource {resource_code}: {e}")
            return []
    
    def analyze_item_capabilities(self, item_code: str) -> Dict:
        """
        Analyze an item's capabilities including stats and crafting potential.
        
        Args:
            item_code: The item code (e.g., "ash_wood", "wooden_staff")
            
        Returns:
            Dictionary with item stats, effects, and crafting info
        """
        try:
            if item_code not in self._item_cache:
                logger.info(f"🔍 Analyzing item: {item_code}")
                response = get_item_api(client=self.client, code=item_code)
                self._item_cache[item_code] = response
            
            item = self._item_cache[item_code]
            capabilities = {
                "name": item.data.name,
                "code": item.data.code,
                "level": item.data.level,
                "type": item.data.type_,
                "subtype": item.data.subtype,
                "effects": [],
                "can_craft": False,
                "craft_requirements": []
            }
            
            # Analyze effects (stats like attack power)
            if hasattr(item.data, 'effects') and item.data.effects is not UNSET and item.data.effects:
                for effect in item.data.effects:
                    effect_info = {
                        "name": effect.code,
                        "value": effect.value
                    }
                    capabilities["effects"].append(effect_info)
                    logger.info(f"  ⚔️ Effect: {effect.code} = {effect.value}")
            
            # Analyze crafting requirements
            if hasattr(item.data, 'craft') and item.data.craft is not UNSET and item.data.craft:
                capabilities["can_craft"] = True
                if hasattr(item.data.craft, 'items') and item.data.craft.items:
                    for ingredient in item.data.craft.items:
                        requirement = {
                            "code": ingredient.code,
                            "quantity": ingredient.quantity
                        }
                        capabilities["craft_requirements"].append(requirement)
                        logger.info(f"  🔨 Crafting requires: {ingredient.quantity}x {ingredient.code}")
            
            return capabilities
            
        except Exception as e:
            logger.error(f"❌ Failed to analyze item {item_code}: {e}")
            return {}
    
    def analyze_upgrade_chain(self, resource_code: str, target_item_code: str) -> Dict:
        """
        Analyze a complete upgrade chain from resource to target item.
        
        Args:
            resource_code: Starting resource (e.g., "ash_tree")
            target_item_code: Target item (e.g., "wooden_staff")
            
        Returns:
            Dictionary with complete chain analysis including upgrade viability
        """
        logger.info(f"🔗 Analyzing upgrade chain: {resource_code} → {target_item_code}")
        
        # Step 1: Analyze resource drops
        drops = self.analyze_resource_drops(resource_code)
        if not drops:
            return {"viable": False, "reason": f"No drops found for {resource_code}"}
        
        # Step 2: Find crafting path to target item
        target_capabilities = self.analyze_item_capabilities(target_item_code)
        if not target_capabilities:
            return {"viable": False, "reason": f"Cannot analyze {target_item_code}"}
        
        # Step 3: Check if any drops can be used to craft target
        viable_paths = []
        for drop in drops:
            drop_code = drop["item_code"]
            
            # Check if this drop is a direct ingredient for target
            for requirement in target_capabilities.get("craft_requirements", []):
                if requirement["code"] == drop_code:
                    path = {
                        "resource": resource_code,
                        "intermediate": drop_code,
                        "target": target_item_code,
                        "drop_rate": drop["drop_rate"],
                        "required_quantity": requirement["quantity"],
                        "target_effects": target_capabilities.get("effects", [])
                    }
                    viable_paths.append(path)
                    logger.info(f"  ✅ Viable path found: {resource_code} → {drop_code} → {target_item_code}")
        
        return {
            "viable": len(viable_paths) > 0,
            "paths": viable_paths,
            "resource_drops": drops,
            "target_capabilities": target_capabilities
        }
    
    def compare_weapon_upgrades(self, current_weapon: str, potential_upgrade: str) -> Dict:
        """
        Compare two weapons to determine if upgrade is worthwhile.
        
        Args:
            current_weapon: Current weapon code (e.g., "wooden_stick")
            potential_upgrade: Potential upgrade code (e.g., "wooden_staff")
            
        Returns:
            Dictionary with comparison results and recommendation
        """
        logger.info(f"⚖️ Comparing weapons: {current_weapon} vs {potential_upgrade}")
        
        current_caps = self.analyze_item_capabilities(current_weapon)
        upgrade_caps = self.analyze_item_capabilities(potential_upgrade)
        
        if not current_caps or not upgrade_caps:
            return {"recommendUpgrade": False, "reason": "Cannot analyze one or both weapons"}
        
        # Find attack effects
        current_attack = 0
        upgrade_attack = 0
        
        for effect in current_caps.get("effects", []):
            if effect["name"].lower() in ["attack", "attack_air", "attack_earth", "attack_fire", "attack_water"]:
                current_attack += effect["value"]
        
        for effect in upgrade_caps.get("effects", []):
            if effect["name"].lower() in ["attack", "attack_air", "attack_earth", "attack_fire", "attack_water"]:
                upgrade_attack += effect["value"]
        
        attack_improvement = upgrade_attack - current_attack
        
        comparison = {
            "current_weapon": current_caps["name"],
            "current_attack": current_attack,
            "upgrade_weapon": upgrade_caps["name"],
            "upgrade_attack": upgrade_attack,
            "attack_improvement": attack_improvement,
            "recommendUpgrade": attack_improvement > 0,
            "reason": f"Attack power {'increases' if attack_improvement > 0 else 'decreases'} by {abs(attack_improvement)}"
        }
        
        logger.info(f"  📊 {comparison['reason']}")
        return comparison
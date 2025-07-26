"""
GOAP planning scenario fixtures for testing

This module provides various planning scenarios including goal states,
action sequences, and planning challenges for comprehensive testing
of the GOAP planning system.
"""

from typing import Any

from src.ai_player.state.game_state import GameState


class PlanningScenarioFixtures:
    """Collection of GOAP planning scenarios for testing"""

    @staticmethod
    def get_basic_leveling_scenario() -> dict[str, Any]:
        """Basic character leveling scenario"""
        return {
            "name": "basic_leveling",
            "description": "Character needs to gain experience to level up",
            "start_state": {
                GameState.CHARACTER_LEVEL: 5,
                GameState.CHARACTER_XP: 1200,
                GameState.HP_CURRENT: 100,
                GameState.HP_MAX: 100,
                GameState.CURRENT_X: 0,
                GameState.CURRENT_Y: 0,
                GameState.COOLDOWN_READY: True,
                GameState.CAN_FIGHT: True,
                GameState.CAN_MOVE: True,
                GameState.WEAPON_EQUIPPED: "iron_sword",
                GameState.AT_SAFE_LOCATION: True
            },
            "goal_state": {
                GameState.CHARACTER_LEVEL: 6,
                GameState.CHARACTER_XP: 1500
            },
            "expected_plan_length": 4,
            "expected_actions": ["move_to_forest", "fight_goblin", "fight_goblin", "rest"],
            "difficulty": "easy",
            "estimated_cost": 15
        }

    @staticmethod
    def get_resource_gathering_scenario() -> dict[str, Any]:
        """Resource gathering scenario"""
        return {
            "name": "resource_gathering",
            "description": "Character needs to gather specific resources",
            "start_state": {
                GameState.CHARACTER_LEVEL: 8,
                GameState.MINING_LEVEL: 6,
                GameState.CURRENT_X: 10,
                GameState.CURRENT_Y: 15,
                GameState.COOLDOWN_READY: True,
                GameState.CAN_GATHER: True,
                GameState.CAN_MOVE: True,
                GameState.TOOL_EQUIPPED: "iron_pickaxe",
                GameState.INVENTORY_SPACE_AVAILABLE: 15,
                GameState.ITEM_QUANTITY: 0
            },
            "goal_state": {
                GameState.ITEM_QUANTITY: 10,  # Need 10 copper ore
                GameState.AT_RESOURCE_LOCATION: True
            },
            "expected_plan_length": 6,
            "expected_actions": ["move_to_mine", "gather_copper", "gather_copper", "gather_copper", "gather_copper", "gather_copper"],
            "difficulty": "easy",
            "estimated_cost": 18
        }

    @staticmethod
    def get_complex_crafting_scenario() -> dict[str, Any]:
        """Complex multi-step crafting scenario"""
        return {
            "name": "complex_crafting",
            "description": "Character needs to craft equipment requiring multiple materials",
            "start_state": {
                GameState.CHARACTER_LEVEL: 15,
                GameState.WEAPONCRAFTING_LEVEL: 12,
                GameState.MINING_LEVEL: 10,
                GameState.CURRENT_X: 25,
                GameState.CURRENT_Y: 30,
                GameState.COOLDOWN_READY: True,
                GameState.CAN_CRAFT: True,
                GameState.CAN_GATHER: True,
                GameState.CAN_MOVE: True,
                GameState.TOOL_EQUIPPED: "steel_pickaxe",
                GameState.INVENTORY_SPACE_AVAILABLE: 20,
                GameState.ITEM_QUANTITY: 0,
                GameState.HAS_CRAFTING_MATERIALS: False
            },
            "goal_state": {
                GameState.WEAPON_EQUIPPED: "mithril_sword",
                GameState.HAS_CRAFTING_MATERIALS: True,
                GameState.ITEM_QUANTITY: 1  # Crafted sword
            },
            "expected_plan_length": 10,
            "expected_actions": [
                "move_to_mithril_mine", "gather_mithril_ore", "gather_mithril_ore", "gather_mithril_ore",
                "move_to_smelter", "smelt_mithril_bar", "smelt_mithril_bar",
                "move_to_forge", "craft_mithril_sword", "equip_mithril_sword"
            ],
            "difficulty": "medium",
            "estimated_cost": 45
        }

    @staticmethod
    def get_emergency_survival_scenario() -> dict[str, Any]:
        """Emergency survival scenario with low HP"""
        return {
            "name": "emergency_survival",
            "description": "Character has critically low HP and needs immediate recovery",
            "start_state": {
                GameState.CHARACTER_LEVEL: 12,
                GameState.HP_CURRENT: 8,  # Critically low
                GameState.HP_MAX: 140,
                GameState.CURRENT_X: 40,
                GameState.CURRENT_Y: 50,
                GameState.COOLDOWN_READY: True,
                GameState.HP_CRITICAL: True,
                GameState.SAFE_TO_FIGHT: False,
                GameState.CAN_REST: True,
                GameState.CAN_MOVE: True,
                GameState.CAN_USE_ITEM: True,
                GameState.HAS_CONSUMABLES: True,
                GameState.AT_SAFE_LOCATION: False,
                GameState.ENEMY_NEARBY: True
            },
            "goal_state": {
                GameState.HP_CURRENT: 100,  # Safe HP level
                GameState.HP_CRITICAL: False,
                GameState.AT_SAFE_LOCATION: True,
                GameState.SAFE_TO_FIGHT: True
            },
            "expected_plan_length": 3,
            "expected_actions": ["move_to_safe_area", "use_health_potion", "rest"],
            "difficulty": "hard",
            "estimated_cost": 8,
            "priority": "critical"
        }

    @staticmethod
    def get_inventory_management_scenario() -> dict[str, Any]:
        """Inventory management scenario"""
        return {
            "name": "inventory_management",
            "description": "Character has full inventory and needs to manage items",
            "start_state": {
                GameState.CHARACTER_LEVEL: 18,
                GameState.CURRENT_X: 35,
                GameState.CURRENT_Y: 45,
                GameState.COOLDOWN_READY: True,
                GameState.INVENTORY_FULL: True,
                GameState.INVENTORY_SPACE_AVAILABLE: 0,
                GameState.INVENTORY_SPACE_USED: 20,
                GameState.CAN_TRADE: True,
                GameState.CAN_MOVE: True,
                GameState.CAN_BANK: True,
                GameState.AT_BANK_LOCATION: False,
                GameState.AT_GRAND_EXCHANGE: False,
                GameState.HAS_REQUIRED_ITEMS: True,
                GameState.INVENTORY_OPTIMIZED: False
            },
            "goal_state": {
                GameState.INVENTORY_SPACE_AVAILABLE: 10,
                GameState.INVENTORY_OPTIMIZED: True,
                GameState.INVENTORY_FULL: False
            },
            "expected_plan_length": 5,
            "expected_actions": ["move_to_bank", "deposit_items", "move_to_grand_exchange", "sell_excess_items", "organize_inventory"],
            "difficulty": "medium",
            "estimated_cost": 20
        }

    @staticmethod
    def get_economic_optimization_scenario() -> dict[str, Any]:
        """Economic optimization scenario for profit maximization"""
        return {
            "name": "economic_optimization",
            "description": "Character seeks to maximize profit through trading",
            "start_state": {
                GameState.CHARACTER_LEVEL: 22,
                GameState.CHARACTER_GOLD: 5000,
                GameState.CURRENT_X: 60,
                GameState.CURRENT_Y: 70,
                GameState.COOLDOWN_READY: True,
                GameState.CAN_TRADE: True,
                GameState.CAN_MOVE: True,
                GameState.MARKET_ACCESS: True,
                GameState.AT_GRAND_EXCHANGE: False,
                GameState.PROFITABLE_TRADE_AVAILABLE: True,
                GameState.ARBITRAGE_OPPORTUNITY: True,
                GameState.INVENTORY_SPACE_AVAILABLE: 15,
                GameState.PORTFOLIO_VALUE: 8000
            },
            "goal_state": {
                GameState.CHARACTER_GOLD: 8000,  # 60% profit increase
                GameState.PORTFOLIO_VALUE: 12000,
                GameState.PROFITABLE_TRADE_AVAILABLE: False  # Opportunity taken
            },
            "expected_plan_length": 7,
            "expected_actions": [
                "move_to_grand_exchange", "analyze_market", "buy_underpriced_items",
                "move_to_alternative_market", "sell_items_for_profit", "reinvest_profits", "update_portfolio"
            ],
            "difficulty": "hard",
            "estimated_cost": 30
        }

    @staticmethod
    def get_skill_specialization_scenario() -> dict[str, Any]:
        """Skill specialization scenario"""
        return {
            "name": "skill_specialization",
            "description": "Character focuses on advancing a specific skill",
            "start_state": {
                GameState.CHARACTER_LEVEL: 20,
                GameState.ALCHEMY_LEVEL: 15,
                GameState.ALCHEMY_XP: 5500,
                GameState.CURRENT_X: 80,
                GameState.CURRENT_Y: 90,
                GameState.COOLDOWN_READY: True,
                GameState.CAN_CRAFT: True,
                GameState.CAN_GATHER: True,
                GameState.CAN_MOVE: True,
                GameState.HAS_CRAFTING_MATERIALS: False,
                GameState.INVENTORY_SPACE_AVAILABLE: 12,
                GameState.TOOL_EQUIPPED: "master_alembic"
            },
            "goal_state": {
                GameState.ALCHEMY_LEVEL: 18,
                GameState.ALCHEMY_XP: 7200,
                GameState.HAS_CRAFTING_MATERIALS: True
            },
            "expected_plan_length": 8,
            "expected_actions": [
                "move_to_herb_garden", "gather_rare_herbs", "gather_rare_herbs",
                "move_to_crystal_cave", "gather_magic_crystals",
                "move_to_alchemy_lab", "craft_master_potion", "craft_master_potion"
            ],
            "difficulty": "medium",
            "estimated_cost": 35
        }

    @staticmethod
    def get_impossible_scenario() -> dict[str, Any]:
        """Impossible scenario that should have no valid plan"""
        return {
            "name": "impossible_scenario",
            "description": "Impossible goal that cannot be achieved",
            "start_state": {
                GameState.CHARACTER_LEVEL: 5,
                GameState.HP_CURRENT: 0,  # Dead character
                GameState.COOLDOWN_READY: False,
                GameState.CAN_MOVE: False,
                GameState.CAN_FIGHT: False,
                GameState.CAN_GATHER: False,
                GameState.CAN_CRAFT: False
            },
            "goal_state": {
                GameState.CHARACTER_LEVEL: 45,  # Impossible jump
                GameState.HP_CURRENT: 300,     # Cannot achieve with dead character
                GameState.ALCHEMY_LEVEL: 45    # Impossible skill level
            },
            "expected_plan_length": 0,
            "expected_actions": [],
            "difficulty": "impossible",
            "estimated_cost": float('inf')
        }

    @staticmethod
    def get_multi_goal_scenario() -> dict[str, Any]:
        """Multi-goal scenario requiring balanced progression"""
        return {
            "name": "multi_goal_progression",
            "description": "Character needs to advance multiple aspects simultaneously",
            "start_state": {
                GameState.CHARACTER_LEVEL: 16,
                GameState.CHARACTER_XP: 6500,
                GameState.MINING_LEVEL: 12,
                GameState.WEAPONCRAFTING_LEVEL: 10,
                GameState.CHARACTER_GOLD: 2000,
                GameState.HP_CURRENT: 160,
                GameState.HP_MAX: 160,
                GameState.CURRENT_X: 45,
                GameState.CURRENT_Y: 55,
                GameState.COOLDOWN_READY: True,
                GameState.INVENTORY_SPACE_AVAILABLE: 18,
                GameState.WEAPON_EQUIPPED: "steel_sword"
            },
            "goal_state": {
                GameState.CHARACTER_LEVEL: 18,      # Level progression
                GameState.MINING_LEVEL: 15,         # Skill progression
                GameState.WEAPONCRAFTING_LEVEL: 13, # Crafting advancement
                GameState.CHARACTER_GOLD: 4000,     # Economic growth
                GameState.WEAPON_EQUIPPED: "mithril_sword"  # Equipment upgrade
            },
            "expected_plan_length": 12,
            "expected_actions": [
                "move_to_mine", "gather_materials", "gather_materials", "gather_materials",
                "move_to_monster_area", "fight_monsters", "fight_monsters",
                "move_to_forge", "craft_equipment", "upgrade_weapon",
                "move_to_market", "sell_excess_items"
            ],
            "difficulty": "hard",
            "estimated_cost": 55
        }


class PlanningChallengeFixtures:
    """Collection of challenging planning scenarios for stress testing"""

    @staticmethod
    def get_resource_scarcity_challenge() -> dict[str, Any]:
        """Challenge with limited resource availability"""
        return {
            "name": "resource_scarcity",
            "description": "Limited resources requiring careful planning",
            "start_state": {
                GameState.CHARACTER_LEVEL: 14,
                GameState.CURRENT_X: 30,
                GameState.CURRENT_Y: 40,
                GameState.COOLDOWN_READY: True,
                GameState.INVENTORY_SPACE_AVAILABLE: 5,  # Very limited space
                GameState.CHARACTER_GOLD: 50,           # Very limited gold
                GameState.RESOURCE_AVAILABLE: False,    # Primary resource unavailable
                GameState.RESOURCE_DEPLETED: True,
                GameState.CAN_GATHER: True,
                GameState.CAN_MOVE: True,
                GameState.CAN_TRADE: True
            },
            "goal_state": {
                GameState.ITEM_QUANTITY: 5,
                GameState.CHARACTER_GOLD: 200
            },
            "constraints": {
                "max_moves": 10,        # Limited movement
                "resource_locations": ["distant_mine", "expensive_vendor"],
                "gold_cost_per_item": 30
            },
            "difficulty": "very_hard"
        }

    @staticmethod
    def get_time_pressure_challenge() -> dict[str, Any]:
        """Challenge with time/action limitations"""
        return {
            "name": "time_pressure",
            "description": "Must achieve goal within limited actions",
            "start_state": {
                GameState.CHARACTER_LEVEL: 10,
                GameState.HP_CURRENT: 30,  # Low HP adds pressure
                GameState.HP_MAX: 120,
                GameState.CURRENT_X: 0,
                GameState.CURRENT_Y: 0,
                GameState.COOLDOWN_READY: True,
                GameState.CAN_FIGHT: True,
                GameState.CAN_MOVE: True,
                GameState.CAN_REST: True,
                GameState.ENEMY_NEARBY: True,  # Adds danger
                GameState.AT_SAFE_LOCATION: False
            },
            "goal_state": {
                GameState.CHARACTER_LEVEL: 11,
                GameState.HP_CURRENT: 100,
                GameState.AT_SAFE_LOCATION: True
            },
            "constraints": {
                "max_actions": 8,       # Very limited actions
                "hp_degrades": True,    # HP decreases over time
                "enemy_pursuit": True   # Enemies follow player
            },
            "difficulty": "extreme"
        }

    @staticmethod
    def get_circular_dependency_challenge() -> dict[str, Any]:
        """Challenge with circular dependencies in requirements"""
        return {
            "name": "circular_dependency",
            "description": "Goal requires items that need the goal to obtain",
            "start_state": {
                GameState.CHARACTER_LEVEL: 20,
                GameState.WEAPONCRAFTING_LEVEL: 15,
                GameState.CURRENT_X: 50,
                GameState.CURRENT_Y: 60,
                GameState.COOLDOWN_READY: True,
                GameState.CAN_CRAFT: True,
                GameState.CAN_MOVE: True,
                GameState.CAN_FIGHT: True,
                GameState.WEAPON_EQUIPPED: "steel_sword",
                GameState.HAS_CRAFTING_MATERIALS: False
            },
            "goal_state": {
                GameState.WEAPON_EQUIPPED: "legendary_sword",
                GameState.HAS_CRAFTING_MATERIALS: True
            },
            "constraints": {
                "legendary_materials_require": "legendary_weapon_to_mine",
                "legendary_weapon_requires": "legendary_materials",
                "break_cycle_via": "quest_reward_or_rare_drop"
            },
            "difficulty": "puzzle"
        }


class PlanningTestSuite:
    """Complete test suite for planning scenarios"""

    @staticmethod
    def get_all_basic_scenarios() -> list[dict[str, Any]]:
        """Get all basic planning scenarios"""
        return [
            PlanningScenarioFixtures.get_basic_leveling_scenario(),
            PlanningScenarioFixtures.get_resource_gathering_scenario(),
            PlanningScenarioFixtures.get_emergency_survival_scenario(),
            PlanningScenarioFixtures.get_inventory_management_scenario()
        ]

    @staticmethod
    def get_all_advanced_scenarios() -> list[dict[str, Any]]:
        """Get all advanced planning scenarios"""
        return [
            PlanningScenarioFixtures.get_complex_crafting_scenario(),
            PlanningScenarioFixtures.get_economic_optimization_scenario(),
            PlanningScenarioFixtures.get_skill_specialization_scenario(),
            PlanningScenarioFixtures.get_multi_goal_scenario()
        ]

    @staticmethod
    def get_all_challenge_scenarios() -> list[dict[str, Any]]:
        """Get all challenge scenarios"""
        return [
            PlanningChallengeFixtures.get_resource_scarcity_challenge(),
            PlanningChallengeFixtures.get_time_pressure_challenge(),
            PlanningChallengeFixtures.get_circular_dependency_challenge()
        ]

    @staticmethod
    def get_scenarios_by_difficulty(difficulty: str) -> list[dict[str, Any]]:
        """Get scenarios filtered by difficulty level"""
        all_scenarios = (
            PlanningTestSuite.get_all_basic_scenarios() +
            PlanningTestSuite.get_all_advanced_scenarios() +
            PlanningTestSuite.get_all_challenge_scenarios() +
            [PlanningScenarioFixtures.get_impossible_scenario()]
        )

        return [scenario for scenario in all_scenarios
                if scenario.get('difficulty') == difficulty]

    @staticmethod
    def get_scenario_by_name(name: str) -> dict[str, Any]:
        """Get specific scenario by name"""
        scenario_map = {
            "basic_leveling": PlanningScenarioFixtures.get_basic_leveling_scenario,
            "resource_gathering": PlanningScenarioFixtures.get_resource_gathering_scenario,
            "complex_crafting": PlanningScenarioFixtures.get_complex_crafting_scenario,
            "emergency_survival": PlanningScenarioFixtures.get_emergency_survival_scenario,
            "inventory_management": PlanningScenarioFixtures.get_inventory_management_scenario,
            "economic_optimization": PlanningScenarioFixtures.get_economic_optimization_scenario,
            "skill_specialization": PlanningScenarioFixtures.get_skill_specialization_scenario,
            "multi_goal_progression": PlanningScenarioFixtures.get_multi_goal_scenario,
            "impossible_scenario": PlanningScenarioFixtures.get_impossible_scenario,
            "resource_scarcity": PlanningChallengeFixtures.get_resource_scarcity_challenge,
            "time_pressure": PlanningChallengeFixtures.get_time_pressure_challenge,
            "circular_dependency": PlanningChallengeFixtures.get_circular_dependency_challenge
        }

        if name not in scenario_map:
            raise ValueError(f"Unknown scenario: {name}. Available: {list(scenario_map.keys())}")

        return scenario_map[name]()


class PlanningExpectedResults:
    """Expected results for planning scenarios to validate test outcomes"""

    @staticmethod
    def get_expected_results() -> dict[str, dict[str, Any]]:
        """Get expected results for all scenarios"""
        return {
            "basic_leveling": {
                "plan_found": True,
                "plan_length_range": (3, 6),
                "total_cost_range": (10, 20),
                "contains_actions": ["move", "fight"],
                "plan_efficiency": "good"
            },
            "resource_gathering": {
                "plan_found": True,
                "plan_length_range": (5, 8),
                "total_cost_range": (15, 25),
                "contains_actions": ["move", "gather"],
                "plan_efficiency": "good"
            },
            "complex_crafting": {
                "plan_found": True,
                "plan_length_range": (8, 12),
                "total_cost_range": (35, 55),
                "contains_actions": ["move", "gather", "craft"],
                "plan_efficiency": "moderate"
            },
            "emergency_survival": {
                "plan_found": True,
                "plan_length_range": (2, 4),
                "total_cost_range": (5, 12),
                "contains_actions": ["move", "rest"],
                "plan_efficiency": "excellent",
                "priority": "critical"
            },
            "inventory_management": {
                "plan_found": True,
                "plan_length_range": (4, 7),
                "total_cost_range": (15, 25),
                "contains_actions": ["move", "bank", "sell"],
                "plan_efficiency": "good"
            },
            "economic_optimization": {
                "plan_found": True,
                "plan_length_range": (6, 10),
                "total_cost_range": (25, 40),
                "contains_actions": ["move", "trade", "analyze"],
                "plan_efficiency": "moderate"
            },
            "impossible_scenario": {
                "plan_found": False,
                "plan_length_range": (0, 0),
                "total_cost_range": (0, 0),
                "contains_actions": [],
                "plan_efficiency": "impossible"
            }
        }

    @staticmethod
    def validate_plan_result(scenario_name: str, actual_plan: list[dict[str, Any]]) -> dict[str, bool]:
        """Validate actual plan result against expected outcomes"""
        expected = PlanningExpectedResults.get_expected_results().get(scenario_name, {})

        if not expected:
            return {"validation_available": False}

        validation_results = {}

        # Check if plan was found
        plan_found = len(actual_plan) > 0
        validation_results["plan_found"] = plan_found == expected.get("plan_found", True)

        # Check plan length
        plan_length = len(actual_plan)
        length_range = expected.get("plan_length_range", (0, float('inf')))
        validation_results["plan_length_valid"] = length_range[0] <= plan_length <= length_range[1]

        # Check total cost
        total_cost = sum(action.get('cost', 0) for action in actual_plan)
        cost_range = expected.get("total_cost_range", (0, float('inf')))
        validation_results["cost_valid"] = cost_range[0] <= total_cost <= cost_range[1]

        # Check required actions
        action_names = [action.get('name', '') for action in actual_plan]
        required_actions = expected.get("contains_actions", [])
        validation_results["required_actions_present"] = all(
            any(req_action in action_name for action_name in action_names)
            for req_action in required_actions
        )

        # Overall validation
        validation_results["overall_valid"] = all(validation_results.values())

        return validation_results


# Convenience functions for test usage
def get_planning_scenario(name: str) -> dict[str, Any]:
    """Get a planning scenario by name"""
    return PlanningTestSuite.get_scenario_by_name(name)


def get_scenarios_for_testing(difficulty: str = "easy") -> list[dict[str, Any]]:
    """Get scenarios suitable for testing by difficulty"""
    return PlanningTestSuite.get_scenarios_by_difficulty(difficulty)


def validate_planning_result(scenario_name: str, plan: list[dict[str, Any]]) -> bool:
    """Quick validation of planning result"""
    validation = PlanningExpectedResults.validate_plan_result(scenario_name, plan)
    return validation.get("overall_valid", False)

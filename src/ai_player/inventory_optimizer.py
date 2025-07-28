"""
Inventory and Bank Optimization System for ArtifactsMMO AI Player

This module provides backwards-compatible imports for the inventory optimization system.
All classes have been refactored into logical groups following the one-class-per-file
principle while maintaining the same import interface.
"""

# Import all classes from their logical group files
from .inventory_models import (
    ItemPriority, InventoryAction, ItemInfo, InventoryState, 
    BankState, OptimizationRecommendation
)
from .inventory_analysis import ItemAnalyzer
from .inventory_optimization import InventoryOptimizer
from .inventory_banking import BankManager
from .inventory_goals import InventoryGoalGenerator
from .inventory_automation import AutoInventoryManager
from .inventory_actions import InventoryActionExecutor

# Re-export all classes for backwards compatibility
__all__ = [
    # Enums and Models
    "ItemPriority",
    "InventoryAction",
    "ItemInfo",
    "InventoryState",
    "BankState",
    "OptimizationRecommendation",
    
    # Analysis
    "ItemAnalyzer",
    
    # Core Optimization
    "InventoryOptimizer",
    
    # Banking
    "BankManager",
    
    # Goal Generation
    "InventoryGoalGenerator",
    
    # Automation
    "AutoInventoryManager",
    
    # Action Execution
    "InventoryActionExecutor"
]
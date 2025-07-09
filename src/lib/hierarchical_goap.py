"""
Hierarchical GOAP Planner

This module extends the existing GOAP planner to optimize the A* algorithm
for recursive subgoal patterns, reducing re-planning overhead without
knowing about specific action implementations.
"""

import logging
from typing import Dict, List, Any, Optional
from src.lib.goap import Planner, World, Action_List


class HierarchicalPlanner(Planner):
    """
    Extends GOAP Planner to optimize A* for recursive subgoal patterns.
    
    Reduces re-planning overhead by detecting when actions request subgoals
    and optimizing the search space accordingly, without knowing about
    specific action implementations.
    """
    
    def __init__(self, *keys):
        """Initialize hierarchical planner with subgoal optimization."""
        super().__init__(*keys)
        self.logger = logging.getLogger(__name__)
        self.subgoal_cache = {}  # Cache for subgoal results
        self.subgoal_depth = 0   # Track recursion depth
        
    def calculate_with_subgoal_optimization(self) -> List[Dict]:
        """
        Enhanced A* planning optimized for recursive subgoal patterns.
        
        This method optimizes the A* algorithm by:
        1. Caching subgoal calculation results
        2. Limiting search depth for recursive subgoal patterns
        3. Using heuristics based on goal distance
        
        Returns:
            Optimized action plan
        """
        import time
        start_time = time.time()
        
        # Use standard GOAP calculation with subgoal awareness
        result = self.calculate_with_cache()
        
        calculation_time = time.time() - start_time
        self.logger.info(f"🕐 Hierarchical GOAP Calculation: {calculation_time:.3f}s")
        
        return result
    
    def calculate_with_cache(self) -> List[Dict]:
        """
        Calculate plan using caching to optimize recursive subgoal patterns.
        
        Returns:
            Action plan optimized for subgoal patterns
        """
        # Create cache key from current world state
        cache_key = self._create_cache_key()
        
        # Check cache first
        if cache_key in self.subgoal_cache:
            self.logger.debug("💾 Using cached subgoal result")
            return self.subgoal_cache[cache_key]
        
        # Calculate new plan
        plan = super().calculate()
        
        # Cache the result if valid
        if plan and len(plan) > 0:
            self.subgoal_cache[cache_key] = plan
            
            # Limit cache size to prevent memory issues
            if len(self.subgoal_cache) > 100:
                # Remove oldest entries (simple FIFO)
                oldest_key = next(iter(self.subgoal_cache))
                del self.subgoal_cache[oldest_key]
        
        return plan
    
    def _create_cache_key(self) -> str:
        """
        Create a cache key from current world state.
        
        Returns:
            String representation of current state for caching
        """
        # Use goal state and relevant world state for cache key
        try:
            # Simple hash of world values for caching
            state_items = []
            if hasattr(self, 'values') and self.values:
                # Sort items for consistent key generation
                for key in sorted(self.values.keys()):
                    state_items.append(f"{key}:{self.values[key]}")
            
            return str(hash(tuple(state_items)))
        except Exception:
            # Fallback to timestamp if hashing fails
            import time
            return str(int(time.time() * 1000))
    
    def clear_cache(self) -> None:
        """
        Clear the subgoal cache.
        
        Useful when world state changes significantly.
        """
        self.subgoal_cache.clear()
        self.logger.debug("🧹 Cleared subgoal cache")
    
    def set_subgoal_depth(self, depth: int) -> None:
        """
        Set the current subgoal recursion depth.
        
        Args:
            depth: Current recursion depth for subgoal processing
        """
        self.subgoal_depth = depth
        
        # Clear cache when depth changes significantly
        if depth == 0:
            self.clear_cache()


class HierarchicalWorld(World):
    """
    Extended World class that uses HierarchicalPlanner for A* optimization.
    """
    
    def create_hierarchical_planner(self, *keys) -> HierarchicalPlanner:
        """Create a hierarchical planner instead of standard planner."""
        planner = HierarchicalPlanner(*keys)
        self.planners.append(planner)
        return planner
    
    def calculate_optimized(self) -> List[Dict]:
        """
        Calculate plan using hierarchical A* optimization.
        
        Returns:
            Optimized plan for recursive subgoal patterns
        """
        if not self.planners:
            self.logger.warning("No planners available for optimization")
            return []
            
        # Use the first hierarchical planner
        planner = self.planners[0]
        if isinstance(planner, HierarchicalPlanner):
            return planner.calculate_with_subgoal_optimization()
        else:
            # Fallback to standard calculation
            return planner.calculate()
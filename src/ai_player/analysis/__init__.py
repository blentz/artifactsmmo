"""
Strategic Analysis Modules

This package provides data-driven analysis modules for intelligent decision making
in the enhanced goal system. All modules use cached game data to make strategic
evaluations without hardcoded values.
"""

from .crafting_analysis import CraftingAnalysisModule
from .level_targeting import LevelAppropriateTargeting
from .map_analysis import MapAnalysisModule

__all__ = [
    "CraftingAnalysisModule",
    "LevelAppropriateTargeting",
    "MapAnalysisModule",
]

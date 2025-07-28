"""
Core Data Models for ArtifactsMMO AI Player

This module contains Pydantic models that align with the artifactsmmo-api-client
models. These models serve as the bridge between the API client responses and
the internal AI player system, providing type safety and validation while
maintaining field name compatibility with the API.

All models in this module are designed to:
1. Have exact field name alignment with artifactsmmo-api-client models
2. Use Pydantic for validation and type safety
3. Support easy conversion to/from API client model instances
4. Integrate seamlessly with the GameState enum system
"""

from .character import Character
from .item import Item, ItemEffect, ItemCondition, CraftRequirement
from .location import MapLocation, MapContent
from .monster import Monster, DropRate
from .resource import Resource, ResourceDrop
from .task import Task, TaskReward

__all__ = [
    "Character",
    "Item",
    "ItemEffect", 
    "ItemCondition",
    "CraftRequirement",
    "MapLocation",
    "MapContent",
    "Monster",
    "DropRate", 
    "Resource",
    "ResourceDrop",
    "Task",
    "TaskReward",
]
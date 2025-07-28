"""
Task Management System for ArtifactsMMO AI Player

This module provides backwards-compatible imports for the task management system.
All classes have been refactored into logical groups following the one-class-per-file
principle while maintaining the same import interface.
"""

# Import all classes from their logical group files
from .task_models import (
    TaskType, TaskPriority, TaskProgress, TaskReward, TaskRequirement, Task
)
from .task_management import TaskManager
from .task_goals import TaskGoalGenerator
from .task_tracking import TaskProgressTracker
from .task_optimization import TaskOptimizer

# Re-export all classes for backwards compatibility
__all__ = [
    # Enums and Models
    "TaskType",
    "TaskPriority", 
    "TaskProgress",
    "TaskReward",
    "TaskRequirement",
    "Task",
    
    # Core Management
    "TaskManager",
    
    # Goal Generation
    "TaskGoalGenerator",
    
    # Progress Tracking
    "TaskProgressTracker",
    
    # Optimization
    "TaskOptimizer"
]
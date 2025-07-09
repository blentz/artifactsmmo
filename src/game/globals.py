""" Global Variables and Constants. """

from enum import Enum

BASEURL = "https://api.artifactsmmo.com"
DATA_PREFIX = "data"
CONFIG_PREFIX = "config"


class StringCompatibleEnum(Enum):
    """Base enum class that provides string compatibility for GOAP processing."""
    
    def __str__(self):
        return self.value
    
    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)
    
    def __hash__(self):
        return hash(self.value)


# Common status values used across multiple domains
class CommonStatus(StringCompatibleEnum):
    """Commonly used status values across different contexts."""
    UNKNOWN = "unknown"
    IDLE = "idle"
    READY = "ready"
    COMPLETED = "completed"
    FAILED = "failed"
    
    # Quality levels
    EXCELLENT = "excellent"
    GOOD = "good"  
    FAIR = "fair"
    POOR = "poor"
    
    # Risk levels
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EquipmentStatus(StringCompatibleEnum):
    """Equipment-specific status values."""
    NONE = "none"
    NEEDS_ANALYSIS = "needs_analysis"
    ANALYZING = "analyzing"
    CRAFTING = "crafting"
    READY = CommonStatus.READY.value
    COMPLETED = CommonStatus.COMPLETED.value


class MaterialStatus(StringCompatibleEnum):
    """Material-specific status values."""
    UNKNOWN = CommonStatus.UNKNOWN.value
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"
    NEEDED = "needed"
    GATHERING = "gathering"
    GATHERED_RAW = "gathered_raw"
    REFINING = "refining"
    CHECKING = "checking"
    TRANSFORMED = "transformed"


class CombatStatus(StringCompatibleEnum):
    """Combat-specific status values."""
    IDLE = CommonStatus.IDLE.value
    READY = CommonStatus.READY.value
    IN_COMBAT = "in_combat"
    SEARCHING = "searching"
    NOT_VIABLE = "not_viable"
    COMPLETED = CommonStatus.COMPLETED.value


class GoalStatus(StringCompatibleEnum):
    """Goal progress status values."""
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = CommonStatus.COMPLETED.value
    FAILED = CommonStatus.FAILED.value


class AnalysisStatus(StringCompatibleEnum):
    """Analysis process status values."""
    UNKNOWN = CommonStatus.UNKNOWN.value
    ANALYZING = "analyzing"
    COMPLETE = "complete"
    COMBAT_READY = "combat_ready"


class SearchStatus(StringCompatibleEnum):
    """Search and discovery status values."""
    UNKNOWN = CommonStatus.UNKNOWN.value
    SEARCHING = "searching"
    DISCOVERED = "discovered"
    FOUND = "found"
    NOT_FOUND = "not_found"


class WorkshopStatus(StringCompatibleEnum):
    """Workshop discovery and access status values."""
    UNKNOWN = CommonStatus.UNKNOWN.value
    DISCOVERED = "discovered"
    AVAILABLE = "available"
    BUSY = "busy"


class HealingStatus(StringCompatibleEnum):
    """Healing process status values."""
    IDLE = CommonStatus.IDLE.value
    NEEDED = "needed"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


class QualityLevel(StringCompatibleEnum):
    """Quality/performance evaluation levels."""
    UNKNOWN = CommonStatus.UNKNOWN.value
    INSUFFICIENT_DATA = "insufficient_data"
    EXCELLENT = CommonStatus.EXCELLENT.value
    GOOD = CommonStatus.GOOD.value
    FAIR = CommonStatus.FAIR.value
    POOR = CommonStatus.POOR.value
    VERY_POOR = "very_poor"


class CombatRecommendation(StringCompatibleEnum):
    """Combat strategy recommendations."""
    ASSESS_SITUATION = "assess_situation"
    IMPROVE_READINESS = "improve_readiness"
    AVOID_COMBAT = "avoid_combat"
    ENGAGE_COMBAT = "engage_combat"
    CAUTIOUS_COMBAT = "cautious_combat"
    LIMITED_COMBAT = "limited_combat"


class RiskLevel(StringCompatibleEnum):
    """Risk assessment levels."""
    LOW = CommonStatus.LOW.value
    MEDIUM = CommonStatus.MEDIUM.value
    HIGH = CommonStatus.HIGH.value
    UNKNOWN = CommonStatus.UNKNOWN.value





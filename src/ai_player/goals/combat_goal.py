"""
Combat Goal Implementation

This module implements intelligent combat goal selection that targets level-appropriate
monsters for optimal XP progression toward level 5, using data-driven analysis and
strategic monster selection without hardcoded values.
"""


from ..analysis.level_targeting import LevelAppropriateTargeting
from ..analysis.map_analysis import MapAnalysisModule
from ..state.character_game_state import CharacterGameState
from ..state.game_state import GameState
from src.game_data.game_data import GameData
from ..types.goap_models import GOAPTargetState
from .base_goal import BaseGoal
from .sub_goal_request import SubGoalRequest


class CombatGoal(BaseGoal):
    """Intelligent combat goal for level-appropriate monster targeting.

    This goal implements strategic combat planning using the LevelAppropriateTargeting
    analysis module to select optimal monsters for XP progression toward level 5,
    with safety considerations and sub-goal request generation for dependencies.
    """

    def __init__(self, target_monster_code: str | None = None, min_hp_percentage: float = 0.4):
        """Initialize combat goal with optional target specification.

        Parameters:
            target_monster_code: Optional specific monster code to target
            min_hp_percentage: Minimum HP percentage required for safe combat
        """
        self.target_monster_code = target_monster_code
        self.min_hp_percentage = min_hp_percentage
        self.level_targeting = LevelAppropriateTargeting()
        self.map_analysis = MapAnalysisModule()

    def calculate_weight(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate combat goal weight using multi-factor scoring.

        This method implements the PRP requirement for weighted scoring:
        - Necessity (40%): XP required for level progression
        - Feasibility (30%): Character can safely engage in combat
        - Progression Value (20%): Direct contribution to level 5 goal
        - Stability (10%): Low error risk for steady advancement
        """
        self.validate_game_data(game_data)

        # Calculate necessity (40% weight)
        current_level = character_state.level
        if current_level >= 5:
            necessity = 0.1  # Low necessity if already at target level
        else:
            # Higher necessity as character approaches level thresholds
            level_progress = (5 - current_level) / 4  # Normalize to 0-1
            necessity = min(1.0, 0.5 + level_progress * 0.5)

        # Calculate feasibility (30% weight)
        feasibility = self._calculate_combat_feasibility(character_state, game_data)

        # Calculate progression value (20% weight)
        progression = self.get_progression_value(character_state)

        # Calculate stability (10% weight)
        error_risk = self.estimate_error_risk(character_state)
        stability = 1.0 - error_risk

        # Combine factors with PRP-specified weights
        final_weight = (necessity * 0.4 + feasibility * 0.3 +
                       progression * 0.2 + stability * 0.1)

        return min(10.0, final_weight * 10.0)  # Scale to 0-10 range

    def is_feasible(self, character_state: CharacterGameState, game_data: GameData) -> bool:
        """Check if combat goal can be pursued safely with current character state."""
        self.validate_game_data(game_data)

        # Check HP threshold for safe combat
        hp_ratio = character_state.hp / max(1, character_state.max_hp)
        if hp_ratio < self.min_hp_percentage:
            return False

        # Check for available level-appropriate monsters
        optimal_monsters = self.level_targeting.find_optimal_monsters(
            character_state.level,
            (character_state.x, character_state.y),
            game_data.monsters,
            game_data.maps
        )

        return len(optimal_monsters) > 0

    def get_target_state(
        self,
        character_state: CharacterGameState,
        game_data: GameData
    ) -> GOAPTargetState:
        """Return GOAP target state for combat goal.
        
        This method defines the desired state conditions for successful combat:
        1. Character must be at a monster location where combat is possible
        2. Character must gain XP through combat actions
        3. Character must maintain minimum HP for safety
        4. Combat must be feasible with current character level
        """
        self.validate_game_data(game_data)

        # Find optimal monster target using analysis module
        current_pos = (character_state.x, character_state.y)

        if self.target_monster_code:
            # Use specific monster if specified
            target_monster = None
            target_location = None

            for monster in game_data.monsters:
                if monster.code == self.target_monster_code:
                    target_monster = monster
                    break

            if target_monster:
                monster_locations = self.map_analysis.find_content_by_code(
                    "monster", self.target_monster_code, game_data.maps
                )
                if monster_locations:
                    # Find nearest location
                    distances = self.map_analysis.calculate_travel_efficiency(
                        current_pos, [(loc.x, loc.y) for loc in monster_locations]
                    )
                    if distances:
                        best_pos = max(distances.keys(), key=lambda pos: distances[pos])
                        target_location = next(loc for loc in monster_locations
                                             if (loc.x, loc.y) == best_pos)
        else:
            # Use analysis module to find optimal monster
            target_monster = None
            target_location = None

            optimal_monsters = self.level_targeting.find_optimal_monsters(
                character_state.level, current_pos, game_data.monsters, game_data.maps
            )

            if optimal_monsters:
                target_monster, target_location, _ = optimal_monsters[0]

        if not target_monster or not target_location:
            # Return empty target state if no feasible combat targets
            return GOAPTargetState(
                target_states={},
                priority=0,
                timeout_seconds=None
            )

        # Define target state conditions for combat success
        target_states = {
            # Must be at monster location for combat
            GameState.AT_MONSTER_LOCATION: True,
            GameState.CURRENT_X: target_location.x,
            GameState.CURRENT_Y: target_location.y,

            # Must gain XP through combat
            GameState.GAINED_XP: True,
            GameState.CAN_GAIN_XP: True,

            # Safety conditions
            GameState.HP_CURRENT: int(character_state.max_hp * self.min_hp_percentage),
            GameState.SAFE_TO_FIGHT: True,

            # Combat readiness
            GameState.CAN_FIGHT: True,
            GameState.COOLDOWN_READY: True,
        }

        return GOAPTargetState(
            target_states=target_states,
            priority=8,  # High priority for progression
            timeout_seconds=300  # 5 minute timeout
        )

    def get_progression_value(self, character_state: CharacterGameState) -> float:
        """Calculate contribution to reaching level 5 with appropriate gear."""
        current_level = character_state.level

        if current_level >= 5:
            return 0.1  # Minimal progression value if already at target

        # Calculate XP contribution toward level 5
        levels_to_go = 5 - current_level
        progression_value = 1.0 - (levels_to_go / 4.0)  # Normalize to 0-1

        return max(0.1, progression_value)

    def estimate_error_risk(self, character_state: CharacterGameState) -> float:
        """Estimate combat-specific error risk."""
        # Combat has inherent risks
        base_risk = 0.4

        # Reduce risk if HP is high
        hp_ratio = character_state.hp / max(1, character_state.max_hp)
        hp_safety_factor = min(0.3, (1.0 - hp_ratio) * 0.5)

        # Increase risk for low-level characters (less experience)
        level_risk_factor = max(0.0, (3 - character_state.level) * 0.1)

        total_risk = base_risk + hp_safety_factor + level_risk_factor
        return min(1.0, total_risk)

    def generate_sub_goal_requests(
        self,
        character_state: CharacterGameState,
        game_data: GameData
    ) -> list[SubGoalRequest]:
        """Generate sub-goal requests for combat dependencies.

        This method identifies runtime dependencies and generates sub-goal requests:
        - Movement to monster location if not already there
        - HP recovery if below safe threshold
        - Equipment upgrades if severely undergeared
        """
        sub_goals = []

        # Check HP requirement
        hp_ratio = character_state.hp / max(1, character_state.max_hp)
        if hp_ratio < self.min_hp_percentage:
            sub_goals.append(SubGoalRequest.reach_hp_threshold(
                self.min_hp_percentage,
                "CombatGoal",
                f"Need {self.min_hp_percentage:.0%} HP for safe combat"
            ))

        # Check if at monster location (simplified check)
        if not character_state.at_monster_location:
            # Find optimal monster location
            optimal_monsters = self.level_targeting.find_optimal_monsters(
                character_state.level,
                (character_state.x, character_state.y),
                game_data.monsters,
                game_data.maps
            )

            if optimal_monsters:
                target_monster, target_location, _ = optimal_monsters[0]
                sub_goals.append(SubGoalRequest.move_to_location(
                    target_location.x,
                    target_location.y,
                    "CombatGoal",
                    f"Move to {target_monster.name} location for combat"
                ))

        return sub_goals

    def _calculate_combat_feasibility(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate combat feasibility score (0.0 to 1.0)."""
        feasibility_score = 0.0

        # HP feasibility (40% of feasibility score)
        hp_ratio = character_state.hp / max(1, character_state.max_hp)
        hp_feasibility = min(1.0, hp_ratio / self.min_hp_percentage)
        feasibility_score += hp_feasibility * 0.4

        # Monster availability (30% of feasibility score)
        optimal_monsters = self.level_targeting.find_optimal_monsters(
            character_state.level,
            (character_state.x, character_state.y),
            game_data.monsters,
            game_data.maps
        )
        monster_availability = min(1.0, len(optimal_monsters) / 3.0)  # Normalize
        feasibility_score += monster_availability * 0.3

        # Equipment readiness (20% of feasibility score)
        # Check if character has basic combat equipment
        equipment_score = 0.5  # Default moderate score
        if character_state.weapon_slot:
            equipment_score += 0.3
        if character_state.helmet_slot or character_state.body_armor_slot:
            equipment_score += 0.2
        equipment_score = min(1.0, equipment_score)
        feasibility_score += equipment_score * 0.2

        # Cooldown readiness (10% of feasibility score)
        cooldown_score = 1.0 if character_state.cooldown_expiration_utc is None else 0.5
        feasibility_score += cooldown_score * 0.1

        return min(1.0, feasibility_score)

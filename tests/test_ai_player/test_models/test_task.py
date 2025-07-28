"""
Tests for Task Data Models

Tests for Pydantic models representing task data from the ArtifactsMMO API,
including TaskReward and Task models with comprehensive validation and
functionality testing.
"""

import pytest
from typing import Any, List
from unittest.mock import Mock

from src.ai_player.models.task import Task, TaskReward


class TestTaskReward:
    """Test TaskReward model functionality"""

    def test_task_reward_creation(self):
        """Test basic TaskReward creation"""
        reward = TaskReward(code="copper", quantity=5)
        
        assert reward.code == "copper"
        assert reward.quantity == 5

    def test_task_reward_validation_positive_quantity(self):
        """Test TaskReward requires positive quantity"""
        with pytest.raises(ValueError):
            TaskReward(code="gold", quantity=0)
        
        with pytest.raises(ValueError):
            TaskReward(code="gold", quantity=-1)

    def test_task_reward_gold_reward(self):
        """Test gold reward creation"""
        reward = TaskReward(code="gold", quantity=100)
        
        assert reward.code == "gold"
        assert reward.quantity == 100

    def test_task_reward_assignment_validation(self):
        """Test TaskReward validates assignment"""
        reward = TaskReward(code="iron", quantity=3)
        
        # Valid assignment
        reward.quantity = 10
        assert reward.quantity == 10
        
        # Invalid assignment should raise error
        with pytest.raises(ValueError):
            reward.quantity = -5


class TestTaskBasicCreation:
    """Test basic Task model creation and validation"""

    def test_task_minimal_creation(self):
        """Test Task creation with minimal required fields"""
        task = Task(code="task1", type="monsters", total=5)
        
        assert task.code == "task1"
        assert task.type == "monsters"
        assert task.total == 5
        assert task.skill is None
        assert task.level is None
        assert task.items is None
        assert task.rewards is None

    def test_task_full_creation(self):
        """Test Task creation with all optional fields"""
        rewards = [TaskReward(code="gold", quantity=100)]
        items = [{"code": "copper_ore", "quantity": 3}]
        
        task = Task(
            code="task2",
            type="items",
            total=10,
            skill="mining",
            level=5,
            items=items,
            rewards=rewards
        )
        
        assert task.code == "task2"
        assert task.type == "items"
        assert task.total == 10
        assert task.skill == "mining"
        assert task.level == 5
        assert task.items == items
        assert task.rewards == rewards

    def test_task_validation_positive_total(self):
        """Test Task requires positive total"""
        with pytest.raises(ValueError):
            Task(code="invalid", type="monsters", total=0)
        
        with pytest.raises(ValueError):
            Task(code="invalid", type="monsters", total=-1)

    def test_task_assignment_validation(self):
        """Test Task validates field assignments"""
        task = Task(code="test", type="monsters", total=5)
        
        # Valid assignment
        task.total = 10
        assert task.total == 10
        
        # Invalid assignment should raise error
        with pytest.raises(ValueError):
            task.total = -1


class TestTaskFromApiTask:
    """Test Task.from_api_task factory method"""

    def test_from_api_task_minimal(self):
        """Test creating Task from minimal API task"""
        api_task = Mock(spec=['code', 'type', 'total'])
        api_task.code = "api_task1"
        api_task.type = "monsters"
        api_task.total = 8
        
        task = Task.from_api_task(api_task)
        
        assert task.code == "api_task1"
        assert task.type == "monsters"
        assert task.total == 8
        assert task.skill is None
        assert task.level is None
        assert task.items is None
        assert task.rewards is None

    def test_from_api_task_with_optional_fields(self):
        """Test creating Task from API task with optional fields"""
        api_task = Mock(spec=['code', 'type', 'total', 'skill', 'level', 'items'])
        api_task.code = "api_task2"
        api_task.type = "items"
        api_task.total = 15
        api_task.skill = "woodcutting"
        api_task.level = 10
        api_task.items = [{"code": "ash_wood", "quantity": 5}]
        
        task = Task.from_api_task(api_task)
        
        assert task.code == "api_task2"
        assert task.type == "items"
        assert task.total == 15
        assert task.skill == "woodcutting"
        assert task.level == 10
        assert task.items == [{"code": "ash_wood", "quantity": 5}]
        assert task.rewards is None

    def test_from_api_task_with_rewards(self):
        """Test creating Task from API task with rewards"""
        # Mock reward objects
        api_reward1 = Mock(spec=['code', 'quantity'])
        api_reward1.code = "gold"
        api_reward1.quantity = 200
        
        api_reward2 = Mock(spec=['code', 'quantity'])
        api_reward2.code = "copper"
        api_reward2.quantity = 3
        
        api_task = Mock(spec=['code', 'type', 'total', 'rewards'])
        api_task.code = "reward_task"
        api_task.type = "monsters"
        api_task.total = 12
        api_task.rewards = [api_reward1, api_reward2]
        
        task = Task.from_api_task(api_task)
        
        assert task.code == "reward_task"
        assert task.type == "monsters"
        assert task.total == 12
        assert task.rewards is not None
        assert len(task.rewards) == 2
        assert task.rewards[0].code == "gold"
        assert task.rewards[0].quantity == 200
        assert task.rewards[1].code == "copper"
        assert task.rewards[1].quantity == 3

    def test_from_api_task_no_rewards_attribute(self):
        """Test creating Task from API task without rewards attribute"""
        api_task = Mock(spec=['code', 'type', 'total'])
        api_task.code = "no_rewards"
        api_task.type = "items"
        api_task.total = 6
        
        task = Task.from_api_task(api_task)
        
        assert task.code == "no_rewards"
        assert task.rewards is None

    def test_from_api_task_empty_rewards(self):
        """Test creating Task from API task with empty rewards"""
        api_task = Mock(spec=['code', 'type', 'total', 'rewards'])
        api_task.code = "empty_rewards"
        api_task.type = "monsters"
        api_task.total = 4
        api_task.rewards = []
        
        task = Task.from_api_task(api_task)
        
        assert task.code == "empty_rewards"
        assert task.rewards is None

    def test_from_api_task_missing_optional_attrs(self):
        """Test creating Task from API task missing optional attributes"""
        api_task = Mock(spec=['code', 'type', 'total'])
        api_task.code = "minimal_api"
        api_task.type = "items"
        api_task.total = 3
        
        task = Task.from_api_task(api_task)
        
        assert task.code == "minimal_api"
        assert task.type == "items"
        assert task.total == 3
        assert task.skill is None
        assert task.level is None
        assert task.items is None


class TestTaskProperties:
    """Test Task property methods"""

    def test_is_combat_task_true(self):
        """Test is_combat_task returns True for monsters type"""
        task = Task(code="combat", type="monsters", total=5)
        assert task.is_combat_task is True

    def test_is_combat_task_case_insensitive(self):
        """Test is_combat_task is case insensitive"""
        task = Task(code="combat", type="MONSTERS", total=5)
        assert task.is_combat_task is True

    def test_is_combat_task_false(self):
        """Test is_combat_task returns False for non-monsters type"""
        task = Task(code="gather", type="items", total=5)
        assert task.is_combat_task is False

    def test_is_gathering_task_true(self):
        """Test is_gathering_task returns True for items type"""
        task = Task(code="gather", type="items", total=8)
        assert task.is_gathering_task is True

    def test_is_gathering_task_case_insensitive(self):
        """Test is_gathering_task is case insensitive"""
        task = Task(code="gather", type="ITEMS", total=8)
        assert task.is_gathering_task is True

    def test_is_gathering_task_false(self):
        """Test is_gathering_task returns False for non-items type"""
        task = Task(code="combat", type="monsters", total=5)
        assert task.is_gathering_task is False

    def test_has_skill_requirement_true(self):
        """Test has_skill_requirement returns True when skill is set"""
        task = Task(code="skill_task", type="items", total=5, skill="mining")
        assert task.has_skill_requirement is True

    def test_has_skill_requirement_false(self):
        """Test has_skill_requirement returns False when skill is None"""
        task = Task(code="no_skill", type="monsters", total=5)
        assert task.has_skill_requirement is False

    def test_has_level_requirement_true(self):
        """Test has_level_requirement returns True when level is set"""
        task = Task(code="level_task", type="items", total=5, level=10)
        assert task.has_level_requirement is True

    def test_has_level_requirement_false(self):
        """Test has_level_requirement returns False when level is None"""
        task = Task(code="no_level", type="monsters", total=5)
        assert task.has_level_requirement is False

    def test_has_item_requirements_true(self):
        """Test has_item_requirements returns True when items exist"""
        items = [{"code": "copper", "quantity": 3}]
        task = Task(code="item_task", type="monsters", total=5, items=items)
        assert task.has_item_requirements is True

    def test_has_item_requirements_false_none(self):
        """Test has_item_requirements returns False when items is None"""
        task = Task(code="no_items", type="monsters", total=5)
        assert task.has_item_requirements is False

    def test_has_item_requirements_false_empty(self):
        """Test has_item_requirements returns False when items is empty"""
        task = Task(code="empty_items", type="monsters", total=5, items=[])
        assert task.has_item_requirements is False

    def test_has_rewards_true(self):
        """Test has_rewards returns True when rewards exist"""
        rewards = [TaskReward(code="gold", quantity=100)]
        task = Task(code="reward_task", type="monsters", total=5, rewards=rewards)
        assert task.has_rewards is True

    def test_has_rewards_false_none(self):
        """Test has_rewards returns False when rewards is None"""
        task = Task(code="no_rewards", type="monsters", total=5)
        assert task.has_rewards is False

    def test_has_rewards_false_empty(self):
        """Test has_rewards returns False when rewards is empty"""
        task = Task(code="empty_rewards", type="monsters", total=5, rewards=[])
        assert task.has_rewards is False


class TestTaskCharacterValidation:
    """Test Task.can_complete_with_character method"""

    def test_can_complete_no_requirements(self):
        """Test character can complete task with no requirements"""
        task = Task(code="simple", type="monsters", total=5)
        character = Mock()
        
        result = task.can_complete_with_character(character)
        assert result is True

    def test_can_complete_level_requirement_met(self):
        """Test character can complete task when level requirement is met"""
        task = Task(code="level_task", type="monsters", total=5, level=10)
        character = Mock()
        character.level = 15
        
        result = task.can_complete_with_character(character)
        assert result is True

    def test_can_complete_level_requirement_not_met(self):
        """Test character cannot complete task when level requirement not met"""
        task = Task(code="level_task", type="monsters", total=5, level=10)
        character = Mock()
        character.level = 8
        
        result = task.can_complete_with_character(character)
        assert result is False

    def test_can_complete_level_requirement_no_character_level(self):
        """Test character without level attribute passes level check"""
        task = Task(code="level_task", type="monsters", total=5, level=10)
        character = Mock(spec=[])  # No attributes
        
        result = task.can_complete_with_character(character)
        assert result is True

    def test_can_complete_skill_requirement_met(self):
        """Test character can complete task when skill requirement is met"""
        task = Task(code="skill_task", type="items", total=5, skill="mining", level=8)
        character = Mock(spec=['mining_level'])
        character.mining_level = 10
        
        result = task.can_complete_with_character(character)
        assert result is True

    def test_can_complete_skill_requirement_not_met(self):
        """Test character cannot complete task when skill requirement not met"""
        task = Task(code="skill_task", type="items", total=5, skill="mining", level=8)
        character = Mock(spec=['mining_level'])
        character.mining_level = 5
        
        result = task.can_complete_with_character(character)
        assert result is False

    def test_can_complete_skill_requirement_no_character_skill(self):
        """Test character without skill attribute passes skill check"""
        task = Task(code="skill_task", type="items", total=5, skill="woodcutting", level=5)
        character = Mock(spec=[])  # No attributes
        
        result = task.can_complete_with_character(character)
        assert result is True

    def test_can_complete_skill_requirement_no_level(self):
        """Test skill requirement without level specified passes"""
        task = Task(code="skill_task", type="items", total=5, skill="fishing")
        character = Mock(spec=['fishing_level'])
        character.fishing_level = 3
        
        result = task.can_complete_with_character(character)
        assert result is True

    def test_can_complete_both_requirements_met(self):
        """Test character can complete task when both level and skill requirements met"""
        task = Task(code="complex_task", type="items", total=5, skill="mining", level=12)
        character = Mock(spec=['level', 'mining_level'])
        character.level = 15
        character.mining_level = 15
        
        result = task.can_complete_with_character(character)
        assert result is True

    def test_can_complete_level_met_skill_not_met(self):
        """Test character cannot complete task when level met but skill not met"""
        task = Task(code="complex_task", type="items", total=5, skill="mining", level=12)
        character = Mock(spec=['level', 'mining_level'])
        character.level = 15
        character.mining_level = 8
        
        result = task.can_complete_with_character(character)
        assert result is False


class TestTaskRewardMethods:
    """Test Task reward-related methods"""

    def test_get_gold_reward_no_rewards(self):
        """Test get_gold_reward returns 0 when no rewards"""
        task = Task(code="no_rewards", type="monsters", total=5)
        
        result = task.get_gold_reward()
        assert result == 0

    def test_get_gold_reward_empty_rewards(self):
        """Test get_gold_reward returns 0 when rewards is empty list"""
        task = Task(code="empty_rewards", type="monsters", total=5, rewards=[])
        
        result = task.get_gold_reward()
        assert result == 0

    def test_get_gold_reward_single_gold(self):
        """Test get_gold_reward returns correct amount for single gold reward"""
        rewards = [TaskReward(code="gold", quantity=150)]
        task = Task(code="gold_task", type="monsters", total=5, rewards=rewards)
        
        result = task.get_gold_reward()
        assert result == 150

    def test_get_gold_reward_multiple_gold(self):
        """Test get_gold_reward sums multiple gold rewards"""
        rewards = [
            TaskReward(code="gold", quantity=100),
            TaskReward(code="copper", quantity=5),
            TaskReward(code="gold", quantity=50)
        ]
        task = Task(code="multi_gold", type="monsters", total=5, rewards=rewards)
        
        result = task.get_gold_reward()
        assert result == 150

    def test_get_gold_reward_case_insensitive(self):
        """Test get_gold_reward is case insensitive"""
        rewards = [
            TaskReward(code="GOLD", quantity=75),
            TaskReward(code="Gold", quantity=25)
        ]
        task = Task(code="case_gold", type="monsters", total=5, rewards=rewards)
        
        result = task.get_gold_reward()
        assert result == 100

    def test_get_gold_reward_no_gold_rewards(self):
        """Test get_gold_reward returns 0 when no gold rewards exist"""
        rewards = [
            TaskReward(code="copper", quantity=10),
            TaskReward(code="iron", quantity=5)
        ]
        task = Task(code="no_gold", type="monsters", total=5, rewards=rewards)
        
        result = task.get_gold_reward()
        assert result == 0

    def test_get_item_rewards_no_rewards(self):
        """Test get_item_rewards returns empty list when no rewards"""
        task = Task(code="no_rewards", type="monsters", total=5)
        
        result = task.get_item_rewards()
        assert result == []

    def test_get_item_rewards_empty_rewards(self):
        """Test get_item_rewards returns empty list when rewards is empty"""
        task = Task(code="empty_rewards", type="monsters", total=5, rewards=[])
        
        result = task.get_item_rewards()
        assert result == []

    def test_get_item_rewards_only_gold(self):
        """Test get_item_rewards returns empty list when only gold rewards"""
        rewards = [
            TaskReward(code="gold", quantity=100),
            TaskReward(code="GOLD", quantity=50)
        ]
        task = Task(code="only_gold", type="monsters", total=5, rewards=rewards)
        
        result = task.get_item_rewards()
        assert result == []

    def test_get_item_rewards_only_items(self):
        """Test get_item_rewards returns all rewards when no gold"""
        rewards = [
            TaskReward(code="copper", quantity=5),
            TaskReward(code="iron", quantity=3)
        ]
        task = Task(code="only_items", type="monsters", total=5, rewards=rewards)
        
        result = task.get_item_rewards()
        assert len(result) == 2
        assert result[0].code == "copper"
        assert result[0].quantity == 5
        assert result[1].code == "iron"
        assert result[1].quantity == 3

    def test_get_item_rewards_mixed_rewards(self):
        """Test get_item_rewards filters out gold from mixed rewards"""
        rewards = [
            TaskReward(code="gold", quantity=100),
            TaskReward(code="copper", quantity=5),
            TaskReward(code="GOLD", quantity=50),
            TaskReward(code="iron", quantity=3)
        ]
        task = Task(code="mixed_rewards", type="monsters", total=5, rewards=rewards)
        
        result = task.get_item_rewards()
        assert len(result) == 2
        assert result[0].code == "copper"
        assert result[0].quantity == 5
        assert result[1].code == "iron"
        assert result[1].quantity == 3


class TestTaskEdgeCases:
    """Test edge cases and error conditions"""

    def test_task_with_none_skill_but_level(self):
        """Test task with None skill but level set behaves correctly"""
        task = Task(code="edge_case", type="items", total=5, skill=None, level=10)
        
        assert not task.has_skill_requirement
        assert task.has_level_requirement
        
        character = Mock()
        character.level = 15
        assert task.can_complete_with_character(character) is True

    def test_task_reward_string_representation(self):
        """Test TaskReward can be represented as string"""
        reward = TaskReward(code="gold", quantity=100)
        
        # Should not raise an exception
        str_repr = str(reward)
        assert "gold" in str_repr
        assert "100" in str_repr

    def test_task_string_representation(self):
        """Test Task can be represented as string"""
        task = Task(code="test_task", type="monsters", total=5)
        
        # Should not raise an exception
        str_repr = str(task)
        assert "test_task" in str_repr
        assert "monsters" in str_repr
        assert "5" in str_repr

    def test_task_with_complex_items_structure(self):
        """Test task with complex items structure"""
        complex_items = [
            {"code": "copper_ore", "quantity": 5, "extra_field": "value"},
            {"code": "iron_ore", "quantity": 3}
        ]
        
        task = Task(code="complex", type="items", total=10, items=complex_items)
        
        assert task.has_item_requirements is True
        assert task.items == complex_items

    def test_task_equality_comparison(self):
        """Test Task equality comparison"""
        task1 = Task(code="same_task", type="monsters", total=5)
        task2 = Task(code="same_task", type="monsters", total=5)
        task3 = Task(code="different_task", type="monsters", total=5)
        
        # Pydantic models should support equality comparison
        assert task1 == task2
        assert task1 != task3
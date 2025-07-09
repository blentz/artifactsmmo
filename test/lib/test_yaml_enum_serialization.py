"""
Tests for YAML enum serialization functionality.

Tests ensure that all custom enums from src.game.globals can be properly
serialized to and from YAML format without errors.
"""

import tempfile
import pytest
from yaml import safe_load, safe_dump

from src.lib.yaml_data import YamlData, enum_representer
from src.game.globals import (
    StringCompatibleEnum, CommonStatus, EquipmentStatus, MaterialStatus,
    CombatStatus, GoalStatus, AnalysisStatus, SearchStatus, WorkshopStatus,
    HealingStatus, QualityLevel, CombatRecommendation, RiskLevel
)


class TestEnumSerialization:
    """Test enum serialization and deserialization in YAML."""

    def test_equipment_status_serialization(self):
        """Test EquipmentStatus enum serialization to YAML."""
        test_data = {
            'equipment_status': {
                'upgrade_status': EquipmentStatus.READY,
                'selected_item': 'copper_dagger'
            }
        }
        
        # Should not raise an exception
        yaml_str = safe_dump(test_data)
        assert 'ready' in yaml_str
        assert 'copper_dagger' in yaml_str
        
        # Should be deserializable
        reloaded = safe_load(yaml_str)
        assert reloaded['equipment_status']['upgrade_status'] == 'ready'
        assert reloaded['equipment_status']['selected_item'] == 'copper_dagger'

    def test_material_status_serialization(self):
        """Test MaterialStatus enum serialization to YAML."""
        test_data = {
            'materials': {
                'status': MaterialStatus.INSUFFICIENT,
                'gathered': False
            }
        }
        
        yaml_str = safe_dump(test_data)
        assert 'insufficient' in yaml_str
        
        reloaded = safe_load(yaml_str)
        assert reloaded['materials']['status'] == 'insufficient'

    def test_combat_status_serialization(self):
        """Test CombatStatus enum serialization to YAML."""
        test_data = {
            'combat_context': {
                'status': CombatStatus.READY,
                'recent_win_rate': 1.0
            }
        }
        
        yaml_str = safe_dump(test_data)
        assert 'ready' in yaml_str
        
        reloaded = safe_load(yaml_str)
        assert reloaded['combat_context']['status'] == 'ready'

    def test_all_enum_classes_serializable(self):
        """Test that all custom enum classes can be serialized."""
        enum_classes = [
            CommonStatus, EquipmentStatus, MaterialStatus, CombatStatus,
            GoalStatus, AnalysisStatus, SearchStatus, WorkshopStatus,
            HealingStatus, QualityLevel, CombatRecommendation, RiskLevel
        ]
        
        for enum_class in enum_classes:
            for enum_value in enum_class:
                test_data = {'test_enum': enum_value}
                
                # Should not raise an exception
                yaml_str = safe_dump(test_data)
                assert enum_value.value in yaml_str
                
                # Should be deserializable
                reloaded = safe_load(yaml_str)
                assert reloaded['test_enum'] == enum_value.value

    def test_complex_state_with_multiple_enums(self):
        """Test complex state structure with multiple enum types."""
        complex_state = {
            'equipment_status': {
                'upgrade_status': EquipmentStatus.READY,
                'selected_item': 'copper_dagger'
            },
            'materials': {
                'status': MaterialStatus.INSUFFICIENT,
                'gathered': False
            },
            'combat_context': {
                'status': CombatStatus.IDLE,
                'recent_win_rate': 1.0
            },
            'goal_progress': {
                'phase': GoalStatus.EXECUTING
            },
            'healing_context': {
                'healing_status': HealingStatus.IDLE
            }
        }
        
        # Should not raise an exception
        yaml_str = safe_dump(complex_state)
        
        # Check all enum values are present as strings
        assert 'ready' in yaml_str
        assert 'insufficient' in yaml_str
        assert 'idle' in yaml_str
        assert 'executing' in yaml_str
        
        # Should be deserializable
        reloaded = safe_load(yaml_str)
        assert reloaded['equipment_status']['upgrade_status'] == 'ready'
        assert reloaded['materials']['status'] == 'insufficient'
        assert reloaded['combat_context']['status'] == 'idle'
        assert reloaded['goal_progress']['phase'] == 'executing'
        assert reloaded['healing_context']['healing_status'] == 'idle'

    def test_yaml_data_class_with_enums(self):
        """Test YamlData class handling enum serialization."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_filename = temp_file.name
            
        try:
            # Create YamlData instance
            yaml_data = YamlData(temp_filename)
            
            # Add enum data
            yaml_data.data = {
                'equipment_status': {
                    'upgrade_status': EquipmentStatus.READY,
                    'selected_item': 'copper_dagger'
                },
                'materials': {
                    'status': MaterialStatus.INSUFFICIENT
                }
            }
            
            # Save should not raise an exception
            yaml_data.save()
            
            # Load in new instance
            new_yaml_data = YamlData(temp_filename)
            
            # Verify data was serialized correctly
            assert new_yaml_data.data['equipment_status']['upgrade_status'] == 'ready'
            assert new_yaml_data.data['materials']['status'] == 'insufficient'
            
        finally:
            import os
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

    def test_enum_representer_function(self):
        """Test the enum_representer function directly."""
        from yaml import SafeDumper
        from io import StringIO
        
        stream = StringIO()
        dumper = SafeDumper(stream)
        
        # Test with EquipmentStatus
        result = enum_representer(dumper, EquipmentStatus.READY)
        # The representer should return a YAML string node
        assert hasattr(result, 'value')
        assert result.value == 'ready'
        
        # Test with MaterialStatus
        result = enum_representer(dumper, MaterialStatus.INSUFFICIENT)
        assert result.value == 'insufficient'

    def test_string_compatible_enum_behavior(self):
        """Test StringCompatibleEnum string compatibility works in YAML context."""
        # Test direct string comparison
        assert EquipmentStatus.READY == 'ready'
        assert MaterialStatus.INSUFFICIENT == 'insufficient'
        
        # Test string conversion
        assert str(EquipmentStatus.READY) == 'ready'
        assert str(MaterialStatus.INSUFFICIENT) == 'insufficient'
        
        # Test in YAML context
        test_data = {'status': EquipmentStatus.READY}
        yaml_str = safe_dump(test_data)
        reloaded = safe_load(yaml_str)
        
        # After YAML round-trip, should still match string value
        assert reloaded['status'] == 'ready'
        assert reloaded['status'] == str(EquipmentStatus.READY)
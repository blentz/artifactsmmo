"""
Comprehensive tests for MapAnalysisModule to achieve 100% code coverage.

This module focuses on testing all code paths, edge cases, and error conditions
in the MapAnalysisModule implementation to ensure complete test coverage.
"""

import pytest
from unittest.mock import Mock

from src.ai_player.analysis.map_analysis import MapAnalysisModule
from src.game_data.models import GameMap


def create_mock_map_content(content_type: str = "monster", code: str = "test_monster"):
    """Create a mock map content object."""
    content = Mock()
    content.type = content_type
    content.code = code
    return content


def create_mock_map(
    x: int = 10,
    y: int = 10,
    content_type: str = "monster",
    content_code: str = "test_monster",
    has_content: bool = True,
    **kwargs
):
    """Create a mock map with specified coordinates and content."""
    game_map = Mock(spec=GameMap)
    game_map.x = x
    game_map.y = y
    
    if has_content:
        game_map.content = create_mock_map_content(content_type, content_code)
    else:
        game_map.content = None
    
    # Add any additional attributes
    for key, value in kwargs.items():
        setattr(game_map, key, value)
    
    return game_map


class TestMapAnalysisModule:
    """Comprehensive tests for MapAnalysisModule class."""

    def test_find_nearest_content_empty_maps(self):
        """Test find_nearest_content raises error with empty maps list."""
        analyzer = MapAnalysisModule()
        
        with pytest.raises(ValueError, match="Cannot find content: maps list is empty"):
            analyzer.find_nearest_content(
                current_pos=(0, 0),
                content_type="monster",
                maps=[]
            )

    def test_find_nearest_content_no_matching_content(self):
        """Test find_nearest_content returns empty list when no content matches."""
        analyzer = MapAnalysisModule()
        
        maps = [
            create_mock_map(x=1, y=1, content_type="resource"),
            create_mock_map(x=2, y=2, content_type="npc"),
            create_mock_map(x=3, y=3, has_content=False)
        ]
        
        result = analyzer.find_nearest_content(
            current_pos=(0, 0),
            content_type="monster",
            maps=maps
        )
        
        assert result == []

    def test_find_nearest_content_with_matches(self):
        """Test find_nearest_content finds and sorts by distance."""
        analyzer = MapAnalysisModule()
        
        maps = [
            create_mock_map(x=5, y=5, content_type="monster", content_code="far_monster"),
            create_mock_map(x=1, y=1, content_type="monster", content_code="close_monster"),
            create_mock_map(x=10, y=10, content_type="resource"),  # Wrong type
            create_mock_map(x=3, y=3, content_type="monster", content_code="mid_monster")
        ]
        
        result = analyzer.find_nearest_content(
            current_pos=(0, 0),
            content_type="monster",
            maps=maps
        )
        
        assert len(result) == 3
        # Should be sorted by distance (nearest first)
        distances = [distance for _, distance in result]
        assert distances == sorted(distances)
        
        # Closest should be (1,1) with distance 2
        closest_map, closest_distance = result[0]
        assert closest_map.x == 1 and closest_map.y == 1
        assert closest_distance == 2

    def test_find_nearest_content_no_content_attribute(self):
        """Test find_nearest_content handles maps without content attribute."""
        analyzer = MapAnalysisModule()
        
        maps = [
            create_mock_map(x=1, y=1, content_type="monster"),
            create_mock_map(x=2, y=2, has_content=False)
        ]
        
        result = analyzer.find_nearest_content(
            current_pos=(0, 0),
            content_type="monster",
            maps=maps
        )
        
        # Should only find the one with content
        assert len(result) == 1

    def test_find_content_by_code_empty_maps(self):
        """Test find_content_by_code raises error with empty maps list."""
        analyzer = MapAnalysisModule()
        
        with pytest.raises(ValueError, match="Cannot find content by code: maps list is empty"):
            analyzer.find_content_by_code(
                content_type="monster",
                content_code="test_monster",
                maps=[]
            )

    def test_find_content_by_code_no_matches(self):
        """Test find_content_by_code returns empty list when no matches found."""
        analyzer = MapAnalysisModule()
        
        maps = [
            create_mock_map(x=1, y=1, content_type="monster", content_code="wrong_monster"),
            create_mock_map(x=2, y=2, content_type="resource", content_code="test_monster"),  # Wrong type
            create_mock_map(x=3, y=3, has_content=False)
        ]
        
        result = analyzer.find_content_by_code(
            content_type="monster",
            content_code="test_monster",
            maps=maps
        )
        
        assert result == []

    def test_find_content_by_code_with_matches(self):
        """Test find_content_by_code finds matching content."""
        analyzer = MapAnalysisModule()
        
        maps = [
            create_mock_map(x=1, y=1, content_type="monster", content_code="test_monster"),
            create_mock_map(x=2, y=2, content_type="monster", content_code="other_monster"),
            create_mock_map(x=3, y=3, content_type="monster", content_code="test_monster"),
            create_mock_map(x=4, y=4, content_type="resource", content_code="test_monster")  # Wrong type
        ]
        
        result = analyzer.find_content_by_code(
            content_type="monster",
            content_code="test_monster",
            maps=maps
        )
        
        assert len(result) == 2
        found_positions = [(m.x, m.y) for m in result]
        assert (1, 1) in found_positions
        assert (3, 3) in found_positions

    def test_calculate_travel_efficiency_empty_targets(self):
        """Test calculate_travel_efficiency returns empty dict for empty targets."""
        analyzer = MapAnalysisModule()
        
        result = analyzer.calculate_travel_efficiency(
            start_pos=(0, 0),
            targets=[]
        )
        
        assert result == {}

    def test_calculate_travel_efficiency_single_target(self):
        """Test calculate_travel_efficiency with single target."""
        analyzer = MapAnalysisModule()
        
        result = analyzer.calculate_travel_efficiency(
            start_pos=(0, 0),
            targets=[(3, 4)]  # Distance = 7
        )
        
        assert len(result) == 1
        assert (3, 4) in result
        assert result[(3, 4)] == 1.0 / 7

    def test_calculate_travel_efficiency_multiple_targets(self):
        """Test calculate_travel_efficiency with multiple targets."""
        analyzer = MapAnalysisModule()
        
        result = analyzer.calculate_travel_efficiency(
            start_pos=(0, 0),
            targets=[(1, 1), (5, 5), (0, 0)]  # Distances: 2, 10, 0
        )
        
        assert len(result) == 3
        assert result[(1, 1)] == 1.0 / 2  # Closer = higher efficiency
        assert result[(5, 5)] == 1.0 / 10
        assert result[(0, 0)] == 1.0 / 1  # Distance 0 becomes 1 to avoid division by zero

    def test_find_safe_locations_empty_maps(self):
        """Test find_safe_locations raises error with empty maps list."""
        analyzer = MapAnalysisModule()
        
        with pytest.raises(ValueError, match="Cannot find safe locations: maps list is empty"):
            analyzer.find_safe_locations(
                current_pos=(0, 0),
                maps=[]
            )

    def test_find_safe_locations_all_safe(self):
        """Test find_safe_locations finds safe locations correctly."""
        analyzer = MapAnalysisModule()
        
        maps = [
            create_mock_map(x=1, y=1, content_type="resource"),  # Safe
            create_mock_map(x=2, y=2, has_content=False),        # Safe (no content)
            create_mock_map(x=3, y=3, content_type="npc"),       # Safe
            create_mock_map(x=15, y=15, content_type="resource") # Too far (distance > 10)
        ]
        
        result = analyzer.find_safe_locations(
            current_pos=(0, 0),
            maps=maps,
            max_distance=10
        )
        
        assert len(result) == 3
        # Should be sorted by distance
        distances = [distance for _, distance in result]
        assert distances == sorted(distances)

    def test_find_safe_locations_with_monsters(self):
        """Test find_safe_locations excludes monster locations."""
        analyzer = MapAnalysisModule()
        
        maps = [
            create_mock_map(x=1, y=1, content_type="monster"),   # Unsafe
            create_mock_map(x=2, y=2, content_type="resource"),  # Safe
            create_mock_map(x=3, y=3, content_type="monster"),   # Unsafe
            create_mock_map(x=4, y=4, has_content=False)         # Safe
        ]
        
        result = analyzer.find_safe_locations(
            current_pos=(0, 0),
            maps=maps,
            max_distance=10
        )
        
        assert len(result) == 2
        safe_positions = [(m.x, m.y) for m, _ in result]
        assert (2, 2) in safe_positions
        assert (4, 4) in safe_positions

    def test_find_safe_locations_distance_filtering(self):
        """Test find_safe_locations respects max_distance parameter."""
        analyzer = MapAnalysisModule()
        
        maps = [
            create_mock_map(x=1, y=1, content_type="resource"),  # Distance 2, within range
            create_mock_map(x=3, y=3, content_type="resource"),  # Distance 6, within range
            create_mock_map(x=10, y=10, content_type="resource") # Distance 20, out of range
        ]
        
        result = analyzer.find_safe_locations(
            current_pos=(0, 0),
            maps=maps,
            max_distance=5
        )
        
        assert len(result) == 1
        safe_map, distance = result[0]
        assert safe_map.x == 1 and safe_map.y == 1
        assert distance == 2

    def test_calculate_optimal_route_empty_waypoints(self):
        """Test calculate_optimal_route returns empty list for empty waypoints."""
        analyzer = MapAnalysisModule()
        
        result = analyzer.calculate_optimal_route(
            start_pos=(0, 0),
            waypoints=[]
        )
        
        assert result == []

    def test_calculate_optimal_route_single_waypoint(self):
        """Test calculate_optimal_route returns single waypoint unchanged."""
        analyzer = MapAnalysisModule()
        
        result = analyzer.calculate_optimal_route(
            start_pos=(0, 0),
            waypoints=[(5, 5)]
        )
        
        assert result == [(5, 5)]

    def test_calculate_optimal_route_multiple_waypoints(self):
        """Test calculate_optimal_route optimizes route through waypoints."""
        analyzer = MapAnalysisModule()
        
        # Create waypoints where greedy nearest-neighbor should pick (1,1) first
        waypoints = [(10, 10), (1, 1), (5, 5)]
        
        result = analyzer.calculate_optimal_route(
            start_pos=(0, 0),
            waypoints=waypoints
        )
        
        assert len(result) == 3
        assert result[0] == (1, 1)  # Nearest to start
        # The algorithm should continue from there

    def test_calculate_optimal_route_greedy_algorithm(self):
        """Test calculate_optimal_route uses greedy nearest-neighbor approach."""
        analyzer = MapAnalysisModule()
        
        # Linear arrangement where greedy should work well
        waypoints = [(3, 0), (1, 0), (2, 0)]
        
        result = analyzer.calculate_optimal_route(
            start_pos=(0, 0),
            waypoints=waypoints
        )
        
        assert len(result) == 3
        assert result[0] == (1, 0)  # Nearest to (0,0)
        assert result[1] == (2, 0)  # Nearest to (1,0)  
        assert result[2] == (3, 0)  # Last remaining

    def test_analyze_area_density_empty_maps(self):
        """Test analyze_area_density raises error with empty maps list."""
        analyzer = MapAnalysisModule()
        
        with pytest.raises(ValueError, match="Cannot analyze area density: maps list is empty"):
            analyzer.analyze_area_density(
                center_pos=(0, 0),
                content_type="monster",
                maps=[]
            )

    def test_analyze_area_density_no_content_in_area(self):
        """Test analyze_area_density with no matching content in area."""
        analyzer = MapAnalysisModule()
        
        maps = [
            create_mock_map(x=1, y=1, content_type="resource"),  # Wrong type
            create_mock_map(x=10, y=10, content_type="monster"), # Too far
            create_mock_map(x=2, y=2, has_content=False)         # No content
        ]
        
        result = analyzer.analyze_area_density(
            center_pos=(0, 0),
            content_type="monster",
            maps=maps,
            radius=5
        )
        
        assert result['center_position'] == (0, 0)
        assert result['radius'] == 5
        assert result['content_type'] == "monster"
        assert result['content_count'] == 0
        assert result['total_locations'] == 2  # (1,1) and (2,2) are within radius 5
        assert result['density_ratio'] == 0.0
        assert result['content_locations'] == []

    def test_analyze_area_density_with_content(self):
        """Test analyze_area_density finds content in area."""
        analyzer = MapAnalysisModule()
        
        maps = [
            create_mock_map(x=1, y=1, content_type="monster"),   # Distance 2, in area, matching
            create_mock_map(x=2, y=2, content_type="monster"),   # Distance 4, in area, matching  
            create_mock_map(x=3, y=3, content_type="resource"),  # Distance 6, out of area (radius=5)
            create_mock_map(x=10, y=10, content_type="monster")  # Distance 20, out of area
        ]
        
        result = analyzer.analyze_area_density(
            center_pos=(0, 0),
            content_type="monster",
            maps=maps,
            radius=5
        )
        
        assert result['content_count'] == 2
        assert result['total_locations'] == 2  # Only (1,1) and (2,2) are within radius 5 from (0,0)
        assert result['density_ratio'] == 2.0 / 2.0  # 2 monster locations out of 2 total locations
        assert len(result['content_locations']) == 2
        assert (1, 1) in result['content_locations']
        assert (2, 2) in result['content_locations']

    def test_find_content_clusters_empty_maps(self):
        """Test find_content_clusters raises error with empty maps list."""
        analyzer = MapAnalysisModule()
        
        with pytest.raises(ValueError, match="Cannot find content clusters: maps list is empty"):
            analyzer.find_content_clusters(
                content_type="monster",
                maps=[]
            )

    def test_find_content_clusters_no_content(self):
        """Test find_content_clusters returns empty list when no content found."""
        analyzer = MapAnalysisModule()
        
        maps = [
            create_mock_map(x=1, y=1, content_type="resource"),
            create_mock_map(x=2, y=2, has_content=False)
        ]
        
        result = analyzer.find_content_clusters(
            content_type="monster",
            maps=maps
        )
        
        assert result == []

    def test_find_content_clusters_single_location(self):
        """Test find_content_clusters with single content location."""
        analyzer = MapAnalysisModule()
        
        maps = [
            create_mock_map(x=5, y=5, content_type="monster", content_code="test_monster")
        ]
        
        result = analyzer.find_content_clusters(
            content_type="monster",
            maps=maps
        )
        
        assert len(result) == 1
        cluster = result[0]
        assert cluster['center'] == (5, 5)
        assert cluster['member_count'] == 1
        assert cluster['locations'] == [(5, 5)]
        assert 'test_monster' in cluster['content_codes']

    def test_find_content_clusters_multiple_separate_locations(self):
        """Test find_content_clusters with separate locations."""
        analyzer = MapAnalysisModule()
        
        maps = [
            create_mock_map(x=1, y=1, content_type="monster", content_code="monster1"),
            create_mock_map(x=10, y=10, content_type="monster", content_code="monster2")  # Far apart
        ]
        
        result = analyzer.find_content_clusters(
            content_type="monster",
            maps=maps,
            cluster_radius=3
        )
        
        assert len(result) == 2  # Two separate clusters
        # Should be sorted by member count (both have 1 member, so order may vary)
        assert all(cluster['member_count'] == 1 for cluster in result)

    def test_find_content_clusters_clustered_locations(self):
        """Test find_content_clusters groups nearby locations."""
        analyzer = MapAnalysisModule()
        
        maps = [
            create_mock_map(x=1, y=1, content_type="monster", content_code="monster1"),
            create_mock_map(x=2, y=2, content_type="monster", content_code="monster2"),  # Close
            create_mock_map(x=3, y=3, content_type="monster", content_code="monster3"),  # Close
            create_mock_map(x=10, y=10, content_type="monster", content_code="monster4") # Far
        ]
        
        result = analyzer.find_content_clusters(
            content_type="monster",
            maps=maps,
            cluster_radius=3
        )
        
        assert len(result) == 2
        # Largest cluster should be first (3 members vs 1 member)
        large_cluster = result[0]
        small_cluster = result[1]
        
        assert large_cluster['member_count'] == 3
        assert small_cluster['member_count'] == 1
        
        # Check that the large cluster contains the close locations
        large_cluster_locations = large_cluster['locations']
        assert (1, 1) in large_cluster_locations
        assert (2, 2) in large_cluster_locations
        assert (3, 3) in large_cluster_locations

    def test_find_content_clusters_center_calculation(self):
        """Test find_content_clusters calculates cluster center correctly."""
        analyzer = MapAnalysisModule()
        
        maps = [
            create_mock_map(x=2, y=2, content_type="monster", content_code="monster1"),
            create_mock_map(x=4, y=4, content_type="monster", content_code="monster2")
        ]
        
        result = analyzer.find_content_clusters(
            content_type="monster",
            maps=maps,
            cluster_radius=5  # Large enough to group them
        )
        
        assert len(result) == 1
        cluster = result[0]
        # Center should be average: ((2+4)//2, (2+4)//2) = (3, 3)
        assert cluster['center'] == (3, 3)
        assert cluster['member_count'] == 2

    @pytest.mark.parametrize("current_pos,content_type,expected_count", [
        ((0, 0), "monster", 3),  # All 3 monster locations: (1,1), (5,5), (15,15)
        ((0, 0), "resource", 1), # One resource at (2,2)
        ((0, 0), "npc", 0),      # No NPC locations
        ((10, 10), "monster", 3), # Still finds all 3 monsters from different position
    ])
    def test_find_nearest_content_various_scenarios(self, current_pos, content_type, expected_count):
        """Test find_nearest_content with various scenarios."""
        analyzer = MapAnalysisModule()
        
        maps = [
            create_mock_map(x=1, y=1, content_type="monster"),
            create_mock_map(x=5, y=5, content_type="monster"),
            create_mock_map(x=2, y=2, content_type="resource"),
            create_mock_map(x=15, y=15, content_type="monster")
        ]
        
        result = analyzer.find_nearest_content(
            current_pos=current_pos,
            content_type=content_type,
            maps=maps
        )
        
        assert len(result) == expected_count

    @pytest.mark.parametrize("radius,expected_locations", [
        (1, 0),  # No locations within radius 1
        (3, 1),  # One location within radius 3: (1,2) at distance 3
        (10, 3), # Three locations within radius 10: all of them
    ])
    def test_analyze_area_density_various_radii(self, radius, expected_locations):
        """Test analyze_area_density with various radius values."""
        analyzer = MapAnalysisModule()
        
        maps = [
            create_mock_map(x=2, y=2, content_type="monster"),   # Distance 4
            create_mock_map(x=1, y=2, content_type="monster"),   # Distance 3
            create_mock_map(x=5, y=5, content_type="monster")    # Distance 10
        ]
        
        result = analyzer.analyze_area_density(
            center_pos=(0, 0),
            content_type="monster",
            maps=maps,
            radius=radius
        )
        
        assert result['total_locations'] == expected_locations
"""Pure glide-path interpolation for the map movement animation."""

import pytest

from artifactsmmo_cli.tui.path_interpolate import glide_path


def test_horizontal_excludes_start_ends_at_end():
    assert glide_path((0, 0), (3, 0), 12) == [(1, 0), (2, 0), (3, 0)]


def test_vertical_negative():
    assert glide_path((0, 0), (0, -2), 12) == [(0, -1), (0, -2)]


def test_diagonal_45():
    assert glide_path((0, 0), (3, 3), 12) == [(1, 1), (2, 2), (3, 3)]


def test_adjacent_is_single_frame():
    assert glide_path((0, 0), (1, 0), 12) == [(1, 0)]


def test_equal_start_end_is_empty():
    assert glide_path((2, 2), (2, 2), 12) == []


def test_long_line_caps_to_max_steps_and_ends_at_end():
    g = glide_path((0, 0), (40, 0), 12)
    assert len(g) == 12
    assert g[-1] == (40, 0)
    xs = [p[0] for p in g]
    assert xs == sorted(xs)          # advances monotonically toward end


def test_non_45_diagonal_ends_at_end_within_cap():
    g = glide_path((0, 0), (4, 2), 12)
    assert g[-1] == (4, 2)
    assert 1 <= len(g) <= 12


def test_max_steps_one_long_line_returns_only_end():
    assert glide_path((0, 0), (5, 0), 1) == [(5, 0)]


def test_max_steps_below_one_raises():
    with pytest.raises(ValueError, match="max_steps"):
        glide_path((0, 0), (3, 0), 0)

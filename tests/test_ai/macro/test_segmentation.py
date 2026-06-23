import pytest

from artifactsmmo_cli.ai.macro.cycle_row import CycleRow
from artifactsmmo_cli.ai.macro.segmentation import Band, segment_bands


def _r(ci, level, goal, char="hero", sess="s1"):
    return CycleRow(char, sess, ci, level, goal, "A", 1, False)


def test_level_bands_cut_on_level_change():
    rows = [_r(0, 1, "G"), _r(1, 1, "G"), _r(2, 2, "G"), _r(3, 1, "G")]
    bands = segment_bands(rows, "level")
    assert [b.key for b in bands] == ["level=1", "level=2", "level=1"]
    assert len(bands[0].rows) == 2


def test_level_bands_separated_by_session_and_character():
    rows = [_r(0, 1, "G", sess="s1"), _r(0, 1, "G", sess="s2"),
            _r(0, 1, "G", char="rob")]
    bands = segment_bands(rows, "level")
    assert len(bands) == 3  # no band spans two sessions or two characters


def test_skill_bands_only_levelskill_goals():
    rows = [_r(0, 3, "GrindCharacterXP(chicken)"),
            _r(1, 3, "LevelSkill(mining->5)"),
            _r(2, 3, "LevelSkill(mining->5)"),
            _r(3, 3, "LevelSkill(woodcutting->5)")]
    bands = segment_bands(rows, "skill")
    assert [b.key for b in bands] == ["LevelSkill(mining->5)", "LevelSkill(woodcutting->5)"]
    assert len(bands[0].rows) == 2


def test_unknown_kind_raises():
    with pytest.raises(ValueError, match="unknown band kind"):
        segment_bands([], "bogus")

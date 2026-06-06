"""DoomedMemo: skip goals that timed out, retry on signature change or after K."""
from artifactsmmo_cli.ai.doomed_memo import DoomedMemo
from tests.test_ai.fixtures import make_state


def test_unmarked_goal_is_not_doomed():
    memo = DoomedMemo(retry_after_cycles=20)
    assert memo.is_doomed("LevelSkill(weaponcrafting->5)", make_state(), cycle=0) is False


def test_marked_goal_is_doomed_same_signature_within_window():
    memo = DoomedMemo(retry_after_cycles=20)
    s = make_state(level=4, skills={"weaponcrafting": 2})
    memo.mark("LevelSkill(weaponcrafting->5)", s, cycle=0)
    assert memo.is_doomed("LevelSkill(weaponcrafting->5)", s, cycle=5) is True


def test_retry_after_k_cycles():
    memo = DoomedMemo(retry_after_cycles=20)
    s = make_state(level=4, skills={"weaponcrafting": 2})
    memo.mark("G", s, cycle=0)
    assert memo.is_doomed("G", s, cycle=19) is True
    assert memo.is_doomed("G", s, cycle=20) is False


def test_retry_on_signature_change():
    memo = DoomedMemo(retry_after_cycles=20)
    memo.mark("G", make_state(level=4, skills={"weaponcrafting": 2}), cycle=0)
    leveled = make_state(level=4, skills={"weaponcrafting": 3})
    assert memo.is_doomed("G", leveled, cycle=1) is False


def test_clear_removes_entry():
    memo = DoomedMemo(retry_after_cycles=20)
    s = make_state()
    memo.mark("G", s, cycle=0)
    memo.clear("G")
    assert memo.is_doomed("G", s, cycle=1) is False

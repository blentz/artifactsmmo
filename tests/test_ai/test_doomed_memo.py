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


def test_ttl_doubles_on_consecutive_failure_same_signature():
    """Second consecutive no-plan under the same signature doubles the
    re-probe window: 20 -> 40."""
    memo = DoomedMemo(retry_after_cycles=20)
    s = make_state(level=4, skills={"weaponcrafting": 2})
    memo.mark("G", s, cycle=0)
    assert memo.is_doomed("G", s, cycle=20) is False  # first re-probe window
    memo.mark("G", s, cycle=20)                       # re-probe also failed
    assert memo.is_doomed("G", s, cycle=59) is True   # 20 + 40 - 1
    assert memo.is_doomed("G", s, cycle=60) is False  # 20 + 40


def test_ttl_keeps_doubling_then_caps():
    """20 -> 40 -> 80 -> 160, then capped at 160 for further failures."""
    memo = DoomedMemo(retry_after_cycles=20, max_retry_after_cycles=160)
    s = make_state(level=4, skills={"weaponcrafting": 2})
    cycle = 0
    for expected_ttl in (20, 40, 80, 160, 160, 160):
        memo.mark("G", s, cycle=cycle)
        assert memo.is_doomed("G", s, cycle=cycle + expected_ttl - 1) is True
        assert memo.is_doomed("G", s, cycle=cycle + expected_ttl) is False
        cycle += expected_ttl


def test_ttl_resets_after_clear():
    """A successful plan (clear) resets the escalation: the next failure
    starts back at the base window."""
    memo = DoomedMemo(retry_after_cycles=20)
    s = make_state(level=4, skills={"weaponcrafting": 2})
    memo.mark("G", s, cycle=0)
    memo.mark("G", s, cycle=20)  # escalated to 40
    memo.clear("G")              # planned successfully
    memo.mark("G", s, cycle=70)
    assert memo.is_doomed("G", s, cycle=89) is True   # base 20 again
    assert memo.is_doomed("G", s, cycle=90) is False


def test_ttl_resets_on_signature_change():
    """A mark under a NEW signature is fresh plannability — the failure
    count restarts at 1 (base window), not at the escalated TTL."""
    memo = DoomedMemo(retry_after_cycles=20)
    s = make_state(level=4, skills={"weaponcrafting": 2})
    memo.mark("G", s, cycle=0)
    memo.mark("G", s, cycle=20)  # escalated to 40 under sig(s)
    leveled = make_state(level=4, skills={"weaponcrafting": 3})
    memo.mark("G", leveled, cycle=30)
    assert memo.is_doomed("G", leveled, cycle=49) is True   # base 20, not 40
    assert memo.is_doomed("G", leveled, cycle=50) is False

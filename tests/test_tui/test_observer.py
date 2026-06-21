"""ThreadSafeBridge tests."""

from unittest.mock import MagicMock

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.tui.observer import ThreadSafeBridge


class _StubApp:
    def __init__(self):
        self.planning_calls = []
    # no call_from_thread -> bridge invokes handler directly


def test_notify_planning_forwards_to_handler():
    app = _StubApp()
    seen = []
    bridge = ThreadSafeBridge(app, lambda s: None, planning_handler=seen.append)
    bridge.notify_planning(True)
    bridge.notify_planning(False)
    assert seen == [True, False]


def _make_snap() -> CycleSnapshot:
    return CycleSnapshot(
        cycle_index=0, timestamp="2026-05-18T00:00:00Z", character="hero",
        x=0, y=0, level=1, xp=0, max_xp=100, hp=100, max_hp=100, gold=0,
        selected_goal="X", action="Y", outcome="ok",
    )


class TestThreadSafeBridge:
    def test_uses_call_from_thread_when_available(self):
        app = MagicMock()
        handler = MagicMock()
        bridge = ThreadSafeBridge(app, handler)
        snap = _make_snap()
        bridge.notify(snap)
        app.call_from_thread.assert_called_once_with(handler, snap)
        handler.assert_not_called()  # routed via app, not direct

    def test_falls_back_to_direct_call(self):
        """Stub apps without call_from_thread: bridge invokes handler directly."""
        class StubApp:
            pass

        handler = MagicMock()
        bridge = ThreadSafeBridge(StubApp(), handler)
        snap = _make_snap()
        bridge.notify(snap)
        handler.assert_called_once_with(snap)

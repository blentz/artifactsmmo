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


def test_notify_planning_no_handler_is_noop():
    """ThreadSafeBridge with no planning_handler: notify_planning must not raise."""
    class _StubAppNoPlanning:
        pass  # no call_from_thread either

    bridge = ThreadSafeBridge(_StubAppNoPlanning(), lambda s: None)
    # Must return early without error — covers the `is None` early-return branch.
    bridge.notify_planning(True)


def test_notify_planning_uses_call_from_thread():
    """When app has call_from_thread, notify_planning routes through it."""
    invoked: list[tuple] = []

    class _StubAppWithThread:
        def call_from_thread(self, cb, *args, **kwargs):
            invoked.append((cb, args, kwargs))
            cb(*args, **kwargs)

    seen: list[bool] = []

    def planning_handler(active: bool) -> None:
        seen.append(active)

    bridge = ThreadSafeBridge(
        _StubAppWithThread(), lambda s: None, planning_handler=planning_handler
    )
    bridge.notify_planning(True)
    assert seen == [True]
    assert len(invoked) == 1
    assert invoked[0][0] is planning_handler

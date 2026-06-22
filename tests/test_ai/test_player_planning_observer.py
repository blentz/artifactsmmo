"""Tests for GamePlayer's planning observer hook."""

from artifactsmmo_cli.ai.player import GamePlayer


class TestPlanningObserver:
    def test_set_planning_observer_stores_callable(self):
        player = GamePlayer(character="hero")
        assert player._planning_observer is None

        def my_handler(active: bool) -> None:
            pass

        player.set_planning_observer(my_handler)
        assert player._planning_observer is my_handler

    def test_notify_planning_calls_observer(self):
        player = GamePlayer(character="hero")
        seen: list[bool] = []
        player.set_planning_observer(seen.append)
        player._notify_planning(True)
        player._notify_planning(False)
        assert seen == [True, False]

    def test_notify_planning_noop_when_none(self):
        """set_planning_observer(None) then _notify_planning must not raise."""
        player = GamePlayer(character="hero")
        player.set_planning_observer(None)
        # Should not raise — covers the `is not None` guard False branch.
        player._notify_planning(True)

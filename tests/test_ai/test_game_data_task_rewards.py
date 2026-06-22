"""GameData task-reward loading: which item codes are earnable by completing tasks."""
from artifactsmmo_cli.ai.game_data import GameData


def _seed(codes: set[str]) -> GameData:
    gd = GameData()
    gd._task_reward_item_codes = frozenset(codes)
    return gd


def test_is_task_earnable_true_for_reward_item():
    gd = _seed({"tasks_coin"})
    assert gd.is_task_earnable("tasks_coin") is True


def test_is_task_earnable_false_for_non_reward_item():
    gd = _seed({"tasks_coin"})
    assert gd.is_task_earnable("copper_ore") is False


def test_task_reward_item_codes_empty_by_default():
    assert GameData().task_reward_item_codes == frozenset()


def test_build_tasks_collects_reward_item_codes():
    gd = GameData()
    gd._build_tasks(_fake_tasks())
    assert "tasks_coin" in gd.task_reward_item_codes


class _FakeItem:
    def __init__(self, code: str) -> None:
        self.code = code


class _FakeRewards:
    def __init__(self, items: list[_FakeItem]) -> None:
        self.items = items


class _FakeTask:
    def __init__(self, items: list[str]) -> None:
        self.rewards = _FakeRewards([_FakeItem(c) for c in items])


def _fake_tasks() -> list[_FakeTask]:
    return [_FakeTask(["tasks_coin"]), _FakeTask(["tasks_coin"])]

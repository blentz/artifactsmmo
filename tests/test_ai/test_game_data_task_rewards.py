"""GameData task-reward loading: which item codes are earnable by completing tasks."""
import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE


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
    def __init__(self, code: str, quantity: int = 0) -> None:
        self.code = code
        self.quantity = quantity


class _FakeRewards:
    def __init__(self, items: list[_FakeItem]) -> None:
        self.items = items


class _FakeTask:
    def __init__(self, items: list[str], code: str = "dummy") -> None:
        self.code = code
        self.rewards = _FakeRewards([_FakeItem(c) for c in items])


def _fake_tasks() -> list[_FakeTask]:
    return [_FakeTask(["tasks_coin"]), _FakeTask(["tasks_coin"])]


def _seed_rewards(rewards: dict[str, int]) -> GameData:
    gd = GameData()
    gd._task_coin_rewards = dict(rewards)
    return gd


def test_task_coin_reward_known_code():
    gd = _seed_rewards({"chicken": 3, "copper_ore": 2})
    assert gd.task_coin_reward("chicken") == 3


def test_task_coin_reward_unknown_code_returns_min_floor():
    gd = _seed_rewards({"chicken": 3, "copper_ore": 2})
    assert gd.task_coin_reward("__pending__") == 2  # conservative min


def test_min_task_coin_reward():
    gd = _seed_rewards({"chicken": 3, "copper_ore": 2})
    assert gd.min_task_coin_reward() == 2


def test_min_task_coin_reward_no_data_raises():
    with pytest.raises(ValueError):
        GameData().min_task_coin_reward()


def test_build_tasks_collects_coin_rewards():
    gd = GameData()
    gd._build_tasks(_fake_coin_tasks())
    assert gd.task_coin_reward("chicken") == 3


class _FakeCoinItem:
    def __init__(self, code: str, quantity: int) -> None:
        self.code = code
        self.quantity = quantity


class _FakeCoinRewards:
    def __init__(self, items: list[_FakeCoinItem]) -> None:
        self.items = items


class _FakeCoinTask:
    def __init__(self, code: str, coin_qty: int) -> None:
        self.code = code
        self.rewards = _FakeCoinRewards([_FakeCoinItem(TASKS_COIN_CODE, coin_qty)])


def _fake_coin_tasks() -> list[_FakeCoinTask]:
    return [_FakeCoinTask("chicken", 3), _FakeCoinTask("copper_ore", 2)]

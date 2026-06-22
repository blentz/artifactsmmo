"""GameData task-reward loading: which item codes are earnable by completing tasks."""
import pytest
from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.game_data_error import GameDataCoverageError
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
        # Use quantity=1 so tasks_coin items pass the ≥1 enforcement at load.
        self.rewards = _FakeRewards([_FakeItem(c, quantity=1) for c in items])


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


def test_build_tasks_rejects_zero_coin_reward():
    """C2: a tasks_coin quantity of 0 must raise at load time (not silently mint 0)."""
    with pytest.raises((GameDataCoverageError, ValueError)):
        GameData()._build_tasks([_FakeCoinTask("chicken", 0)])


def test_fetch_tasks_paginates_until_partial_page():
    """_fetch_tasks fetches page 2 when page 1 is full (100 items), stops on partial."""
    coin_item = MagicMock()
    coin_item.code = TASKS_COIN_CODE
    coin_item.quantity = 1

    def make_task(code: str) -> MagicMock:
        t = MagicMock()
        t.code = code
        t.rewards = MagicMock()
        t.rewards.items = [coin_item]
        return t

    # Page 1: exactly 100 tasks (triggers page 2 fetch)
    page1 = MagicMock()
    page1.data = [make_task(f"monster_{i}") for i in range(100)]
    # Page 2: partial (triggers stop)
    page2 = MagicMock()
    page2.data = [make_task("cow")]

    gd = GameData()
    with patch("artifactsmmo_cli.ai.game_data.get_all_tasks", side_effect=[page1, page2]):
        tasks = gd._fetch_tasks(MagicMock())

    assert len(tasks) == 101
    assert tasks[-1].code == "cow"

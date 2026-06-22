"""Pure core: an acquisition leaf is attainable iff at least one source applies."""
from artifactsmmo_cli.ai.tiers.leaf_attainable_core import leaf_attainable_pure


def test_none_of_the_sources_not_attainable():
    assert leaf_attainable_pure(False, False, False, False) is False


def test_task_earnable_alone_is_attainable():
    # The C1 fix: tasks_coin is earnable even with no other source.
    assert leaf_attainable_pure(False, False, True, False) is True


def test_gatherable_alone_is_attainable():
    assert leaf_attainable_pure(True, False, False, False) is True


def test_known_spawn_drop_alone_is_attainable():
    assert leaf_attainable_pure(False, True, False, False) is True


def test_currency_buy_alone_is_attainable():
    assert leaf_attainable_pure(False, False, False, True) is True

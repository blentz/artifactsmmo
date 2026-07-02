from artifactsmmo_cli.ai.potion_provision_qty import potion_provision_qty_pure


def test_zero_when_slot_filled():
    assert potion_provision_qty_pure(100, 30, 10, True, 100) == 0


def test_zero_when_none_held_or_zero_restore():
    assert potion_provision_qty_pure(100, 30, 0, False, 100) == 0
    assert potion_provision_qty_pure(100, 0, 10, False, 100) == 0


def test_ceil_div_sizing():
    # need 100 HP, 30/potion -> ceil(100/30)=4
    assert potion_provision_qty_pure(100, 30, 10, False, 100) == 4


def test_clamped_by_held():
    assert potion_provision_qty_pure(100, 30, 2, False, 100) == 2


def test_clamped_by_max_stack():
    assert potion_provision_qty_pure(10_000, 30, 500, False, 100) == 100

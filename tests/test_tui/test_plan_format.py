"""short_root: collapse ObtainItem(...) reprs to a scannable short form."""

from artifactsmmo_cli.tui.plan_format import short_root


def test_obtain_quantity_one_drops_quantity():
    assert short_root("ObtainItem(code='copper_boots', quantity=1)") == "copper_boots"


def test_obtain_quantity_many_keeps_count():
    assert short_root("ObtainItem(code='copper_bar', quantity=8)") == "8x copper_bar"


def test_non_obtain_root_unchanged():
    assert short_root("ReachCharLevel(level=6)") == "ReachCharLevel(level=6)"

"""Shared item-table builder tests (no Textual app needed)."""

from rich.console import Console

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.tui.item_tables import build_bank_items, build_inventory_items


def _snap(**overrides) -> CycleSnapshot:
    base = dict(
        cycle_index=1, timestamp="2026-05-21T12:00:00Z", character="hero",
        x=0, y=0, level=5, xp=50, max_xp=500, hp=100, max_hp=100, gold=10,
        selected_goal="g", action="a", outcome="ok",
        inventory={"iron_ore": 5, "ash_wood": 2}, inventory_max=20,
    )
    base.update(overrides)
    return CycleSnapshot(**base)


def _text(renderable) -> str:
    console = Console(no_color=True, width=100)
    with console.capture() as cap:
        console.print(renderable)
    return cap.get()


class TestBuildInventoryItems:
    def test_header_shows_counts(self):
        assert "7/20" in _text(build_inventory_items(_snap()))  # 5 + 2 = 7

    def test_items_listed(self):
        out = _text(build_inventory_items(_snap()))
        assert "iron_ore" in out and "ash_wood" in out

    def test_items_sorted_qty_desc(self):
        out = _text(build_inventory_items(_snap(inventory={"gem": 1, "iron": 10, "wood": 5})))
        assert out.find("iron") < out.find("wood") < out.find("gem")

    def test_no_equipment_section(self):
        assert "Equipment" not in _text(build_inventory_items(_snap()))

    def test_zero_max_no_error(self):
        _text(build_inventory_items(_snap(inventory={}, inventory_max=0)))

    def test_empty_inventory(self):
        _text(build_inventory_items(_snap(inventory={}, inventory_max=20)))


class TestBuildBankItems:
    def test_none_shows_waiting(self):
        out = _text(build_bank_items(_snap(bank_items=None)))
        assert "waiting" in out.lower() and "Bank" in out

    def test_populated_lists_items_and_count(self):
        out = _text(build_bank_items(_snap(bank_items={"gold_ore": 3, "topaz": 1})))
        assert "gold_ore" in out and "topaz" in out
        assert "2 items" in out

    def test_sorted_qty_desc(self):
        out = _text(build_bank_items(_snap(bank_items={"a": 1, "b": 9, "c": 5})))
        assert out.find(" b") < out.find(" c") < out.find(" a")

    def test_empty_dict_zero_items(self):
        out = _text(build_bank_items(_snap(bank_items={})))
        assert "0 items" in out


class TestBankGoldInHeader:
    """The bank's gold is account-wide — one balance every character shares —
    as against the per-character pocket the status pane shows."""

    def test_header_shows_bank_gold(self):
        out = _text(build_bank_items(_snap(bank_items={"copper_ore": 3},
                                           bank_gold=20_000)))
        assert "20,000 gold" in out

    def test_header_still_shows_the_item_count(self):
        out = _text(build_bank_items(_snap(bank_items={"copper_ore": 3, "ash_wood": 1},
                                           bank_gold=20_000)))
        assert "2 items" in out

    def test_unknown_bank_gold_renders_as_a_dash_not_zero(self):
        """A SYNCED bank whose gold was never read is unknown. Rendering 0 would
        claim an observation nobody made."""
        out = _text(build_bank_items(_snap(bank_items={"copper_ore": 3},
                                           bank_gold=None)))
        assert "— gold" in out
        assert "0 gold" not in out

    def test_a_genuinely_empty_bank_shows_zero_not_a_dash(self):
        """0 gold and UNREAD gold are different facts, and the header must say which.

        A falsy check (`if not snap.bank_gold`) passes the unread-renders-as-dash
        test above while collapsing this case into it — claiming the balance was
        never read when in fact it was read and is zero. The `not in` half of this
        assertion is what makes the test bite.
        """
        out = _text(build_bank_items(_snap(bank_items={"copper_ore": 3}, bank_gold=0)))
        assert "0 gold" in out
        assert "— gold" not in out

    def test_unsynced_bank_keeps_its_own_placeholder(self):
        """bank_items is None is a different unknown from bank_gold is None."""
        assert "waiting for sync" in _text(build_bank_items(_snap(bank_items=None)))

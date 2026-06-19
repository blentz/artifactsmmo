"""Behavior tests for formal/sim/capture_base_stats.py.

Uses a fake api_wrapper (records calls, returns canned CharacterSchema-like and
cooldown-bearing responses). time.sleep is monkeypatched to a no-op so cooldown
respect is exercised without real waits. No mocking of the unit under test.
"""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from artifactsmmo_api_client.models.item_slot import ItemSlot

_MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "formal" / "sim" / "capture_base_stats.py"
)
_spec = importlib.util.spec_from_file_location("capture_base_stats", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
capture_base_stats = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(capture_base_stats)


# All CharacterSchema *_slot fields the script reads, so a fake character can be
# constructed with every slot present.
ALL_SLOT_FIELDS = (
    "weapon_slot",
    "rune_slot",
    "shield_slot",
    "helmet_slot",
    "body_armor_slot",
    "leg_armor_slot",
    "boots_slot",
    "ring1_slot",
    "ring2_slot",
    "amulet_slot",
    "artifact1_slot",
    "artifact2_slot",
    "artifact3_slot",
    "utility1_slot",
    "utility2_slot",
    "bag_slot",
)


def _make_character(
    *, level: int, equipped: dict[str, str], stats: dict[str, Any]
) -> SimpleNamespace:
    """Build a CharacterSchema-like object: empty slots default to ""."""
    fields: dict[str, Any] = {field: "" for field in ALL_SLOT_FIELDS}
    fields.update(equipped)
    fields.update(
        {
            "level": level,
            "utility1_slot_quantity": fields.get("_utility1_qty", 1),
            "utility2_slot_quantity": fields.get("_utility2_qty", 1),
        }
    )
    fields.pop("_utility1_qty", None)
    fields.pop("_utility2_qty", None)
    fields.update(stats)
    return SimpleNamespace(**fields)


def _cooldown_response(remaining: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        data=SimpleNamespace(cooldown=SimpleNamespace(remaining_seconds=remaining))
    )


BASE_STATS_GEARED = {
    "max_hp": 999,
    "attack_fire": 50,
    "attack_earth": 0,
    "attack_water": 0,
    "attack_air": 0,
    "res_fire": 10,
    "res_earth": 0,
    "res_water": 0,
    "res_air": 0,
    "critical_strike": 5,
    "initiative": 100,
}

BASE_STATS_BARE = {
    "max_hp": 115,
    "attack_fire": 0,
    "attack_earth": 0,
    "attack_water": 0,
    "attack_air": 0,
    "res_fire": 0,
    "res_earth": 0,
    "res_water": 0,
    "res_air": 0,
    "critical_strike": 0,
    "initiative": 100,
}


class FakeApi:
    """Records the call sequence; returns geared char first, bare char after."""

    def __init__(
        self,
        *,
        level: int,
        equipped: dict[str, str],
        bare_stats: dict[str, Any] | None = None,
        raise_on_second_get: bool = False,
    ):
        self.calls: list[tuple[str, Any]] = []
        self._level = level
        self._equipped = equipped
        self._bare_stats = bare_stats if bare_stats is not None else BASE_STATS_BARE
        self._get_count = 0
        self._raise_on_second_get = raise_on_second_get

    def get_character(self, name: str) -> SimpleNamespace:
        self._get_count += 1
        self.calls.append(("get_character", name))
        if self._get_count == 1:
            return _make_character(
                level=self._level, equipped=self._equipped, stats=BASE_STATS_GEARED
            )
        if self._raise_on_second_get:
            raise ValueError("sampling boom")
        return _make_character(level=self._level, equipped={}, stats=self._bare_stats)

    def action_unequip_item(self, name: str, body: Any) -> SimpleNamespace:
        self.calls.append(("unequip", body.slot))
        return _cooldown_response(remaining=3)

    def action_equip_item(self, name: str, body: Any) -> SimpleNamespace:
        self.calls.append(("equip", (body.slot, body.code)))
        return _cooldown_response(remaining=3)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capture_base_stats.time, "sleep", lambda _seconds: None)


def test_unequip_get_reequip_sequence_in_order(tmp_path: Path) -> None:
    equipped = {"weapon_slot": "wooden_staff", "boots_slot": "leather_boots"}
    api = FakeApi(level=5, equipped=equipped)

    capture_base_stats.capture_base_stats(api, "bob", tmp_path / "out.json")

    kinds = [c[0] for c in api.calls]
    # GET (geared) -> all unequips -> GET (bare) -> all re-equips.
    assert kinds == [
        "get_character",
        "unequip",
        "unequip",
        "get_character",
        "equip",
        "equip",
    ]


def test_empty_slots_are_skipped(tmp_path: Path) -> None:
    equipped = {"weapon_slot": "wooden_staff"}  # only one slot filled
    api = FakeApi(level=5, equipped=equipped)

    capture_base_stats.capture_base_stats(api, "bob", tmp_path / "out.json")

    unequips = [c for c in api.calls if c[0] == "unequip"]
    equips = [c for c in api.calls if c[0] == "equip"]
    assert unequips == [("unequip", ItemSlot.WEAPON)]
    assert equips == [("equip", (ItemSlot.WEAPON, "wooden_staff"))]


def test_captured_row_uses_second_get_values(tmp_path: Path) -> None:
    api = FakeApi(level=1, equipped={"weapon_slot": "wooden_staff"})
    out = tmp_path / "out.json"

    row = capture_base_stats.capture_base_stats(api, "bob", out)

    assert row == {
        "max_hp": 115,
        "attack": {"fire": 0, "earth": 0, "water": 0, "air": 0},
        "resistance": {"fire": 0, "earth": 0, "water": 0, "air": 0},
        "critical_strike": 0,
        "initiative": 100,
    }
    document = json.loads(out.read_text())
    assert document["base_stats"]["1"] == row
    assert "captured_at_1" in document


def test_resumable_merge_two_levels(tmp_path: Path) -> None:
    out = tmp_path / "out.json"

    api1 = FakeApi(level=1, equipped={"weapon_slot": "wooden_staff"})
    capture_base_stats.capture_base_stats(api1, "bob", out)

    api2 = FakeApi(
        level=2,
        equipped={"weapon_slot": "copper_dagger"},
        bare_stats={**BASE_STATS_BARE, "max_hp": 130},
    )
    capture_base_stats.capture_base_stats(api2, "bob", out)

    document = json.loads(out.read_text())
    assert set(document["base_stats"]) == {"1", "2"}
    assert document["base_stats"]["1"]["max_hp"] == 115
    assert document["base_stats"]["2"]["max_hp"] == 130
    assert "captured_at_1" in document
    assert "captured_at_2" in document


def test_restore_runs_even_when_sampling_raises(tmp_path: Path) -> None:
    equipped = {"weapon_slot": "wooden_staff", "amulet_slot": "life_amulet"}
    api = FakeApi(level=5, equipped=equipped, raise_on_second_get=True)

    with pytest.raises(ValueError, match="sampling boom"):
        capture_base_stats.capture_base_stats(api, "bob", tmp_path / "out.json")

    # finally re-equips the ORIGINAL codes despite the raise.
    equips = [c for c in api.calls if c[0] == "equip"]
    assert equips == [
        ("equip", (ItemSlot.WEAPON, "wooden_staff")),
        ("equip", (ItemSlot.AMULET, "life_amulet")),
    ]
    # No JSON written when sampling failed.
    assert not (tmp_path / "out.json").exists()

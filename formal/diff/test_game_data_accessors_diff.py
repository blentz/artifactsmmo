"""Differential test for `Formal.GameDataAccessors` (Phase-9, REAL BUG #16).

Pins the Python `GameData` monster-stat accessors against the Lean
contract. The five accessors `monster_attack`, `monster_resistance`,
`monster_hp`, `monster_critical_strike`, `monster_initiative` raise
`KeyError` on absent codes (post-fix); `monster_level` retains the
documented silent zero default (probe semantics — see game_data.py).

The Lean model is pure (no oracle round-trip): the post-fix contract is
"accessor returns Some iff key present"; the pre-fix bug contract is
"accessor returns the default when absent". Python verification asserts:
* present code ⇒ stored value returned;
* absent code ⇒ `KeyError` raised by the raise-accessors;
* `monster_level` absent ⇒ silent 0 (documented).
"""

from hypothesis import given, settings, strategies as st

import pytest

from artifactsmmo_cli.ai.game_data import GameData

_RAISE_ACCESSORS = (
    "monster_attack",
    "monster_resistance",
    "monster_hp",
    "monster_critical_strike",
    "monster_initiative",
)


def _seed(gd: GameData, codes: list[str]) -> None:
    """Populate every stat dict with the given codes (production
    invariant: `_load_monsters` atomically sets all stat dicts)."""
    for c in codes:
        gd._monster_level[c] = 1
        gd._monster_hp[c] = 10
        gd._monster_attack[c] = {"fire": 1}
        gd._monster_resistance[c] = {}
        gd._monster_critical_strike[c] = 0
        gd._monster_initiative[c] = 0
        gd._monster_type[c] = "normal"


@settings(max_examples=200)
@given(
    present_codes=st.lists(
        st.text(alphabet="abcdefghijklmnop", min_size=1, max_size=6),
        min_size=0, max_size=8, unique=True,
    ),
    probe=st.text(alphabet="abcdefghijklmnop", min_size=1, max_size=6),
)
def test_raise_accessors_match_present_iff_lean(present_codes, probe):
    """Lean role: `accessor_some_iff_present`. Python: present ⇒ returns;
    absent ⇒ KeyError. Both branches pinned per accessor."""
    gd = GameData()
    _seed(gd, present_codes)
    is_present = probe in present_codes
    for name in _RAISE_ACCESSORS:
        method = getattr(gd, name)
        if is_present:
            # Should return the seeded value without raising.
            result = method(probe)
            assert result is not None
        else:
            with pytest.raises(KeyError):
                method(probe)


def test_raise_accessors_boundary_present():
    """Lean role: `accessor_present_witness`. Single-entry seeded map,
    present key returns stored value."""
    gd = GameData()
    _seed(gd, ["chicken"])
    assert gd.monster_attack("chicken") == {"fire": 1}
    assert gd.monster_resistance("chicken") == {}
    assert gd.monster_hp("chicken") == 10
    assert gd.monster_critical_strike("chicken") == 0
    assert gd.monster_initiative("chicken") == 0


def test_raise_accessors_boundary_absent_raises_keyerror():
    """Lean role: `accessor_absent_witness`. Single-entry seeded map,
    absent key raises `KeyError` on every raise-accessor."""
    gd = GameData()
    _seed(gd, ["chicken"])
    for name in _RAISE_ACCESSORS:
        with pytest.raises(KeyError):
            getattr(gd, name)("dragon")


def test_raise_accessors_empty_map_raises_keyerror():
    """Lean role: `accessor_unknown_returns_none`. Empty map, any probe
    raises `KeyError`."""
    gd = GameData()
    for name in _RAISE_ACCESSORS:
        with pytest.raises(KeyError):
            getattr(gd, name)("anything")


def test_monster_level_keeps_silent_zero_probe():
    """Lean role: `monsterLevelProbe_absent_returns_zero` /
    `monsterLevelProbe_present_returns_value`. Documented silent default
    on `monster_level`: probe semantics (is this code a monster?).
    Consumers branch on `> 0` — see game_data.py docstring."""
    gd = GameData()
    assert gd.monster_level("anything") == 0  # silent default, by design
    gd._monster_level["chicken"] = 7
    assert gd.monster_level("chicken") == 7
    assert gd.monster_level("dragon") == 0  # probe still returns 0


def test_predict_win_unknown_monster_no_longer_silent_true():
    """Phase-9 BUG anchor: pre-fix, `predict_win` on an unknown monster
    returned True (silent monster_attack/hp defaults). Post-fix, the
    accessor raises before the verdict — anchoring the load-bearing
    fix. Lean role: `predictWinLite_buggy_unknown_returns_true`
    (pre-fix counterexample) +
    `accessor_unknown_returns_none` (post-fix gate)."""
    from artifactsmmo_cli.ai.combat import predict_win
    from artifactsmmo_cli.ai.world_state import WorldState
    gd = GameData()
    s = WorldState(
        character="c", level=1, xp=0, max_xp=100, hp=100, max_hp=100, gold=0,
        skills={}, x=0, y=0, inventory={}, inventory_max=20,
        inventory_slots_max=20, equipment={},
        cooldown_expires=None, task_code=None, task_type=None,
        task_progress=0, task_total=0,
        bank_items={}, bank_gold=0, pending_items=None,
        attack={"fire": 10, "earth": 0, "water": 0, "air": 0},
    )
    with pytest.raises(KeyError):
        predict_win(s, gd, "xyz_unknown_monster")

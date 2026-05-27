"""Differential test: the real Python upgrade-selection cores
(`best_by_value`, `best_by_key`) must agree with the proved Lean
`bestByValue` / `bestByKey`.

The pure cores live in `artifactsmmo_cli.ai.goals.upgrade_selection` and are the
extracted, store-free heart of `UpgradeEquipmentGoal`'s upgrade ranking:

* `best_by_value(inv, craft)`: higher VALUE; tie -> inventory (the owned pick).
* `best_by_key(cands, key)`: deterministic argmax over `craftable_key` /
  `inventory_key` (lexicographic; item_code, not slot, is the final field).

The Lean oracle models `value` as an exact `Int` (equip_value is integer-valued:
attack + resistance + hp_restore are all ints), and the item_code as `str(code)`
so the String tiebreak matches Python's string ordering on the SAME codes.

We generate candidate lists whose item codes CAN repeat (the real finders emit
one candidate per (item_code, slot), so the same item appears once per slot — the
slot is NOT in the candidate key, so same-code candidates compare EQUAL). With a
small value domain values also repeat, exercising the full tiebreak chain
(relevant -> fills_empty -> value -> -craft_level -> item_code) AND the same-code
tie. Both sides must resolve a tie FIRST-WINS (keep the first equal-key candidate
in list order), which this test pins.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.goals.upgrade_selection import (
    UpgradeCandidate,
    best_by_key,
    best_by_value,
    craftable_key,
    inventory_key,
)
from formal.diff.oracle_client import run_oracle

# small value/level domains so equal values recur and tiebreaks fire often
_VALUE = st.integers(min_value=0, max_value=4)
_LEVEL = st.integers(min_value=0, max_value=3)
_CRAFT = st.integers(min_value=0, max_value=3)
_BOOL = st.booleans()


def _cand(code: int, value: int, level: int, craft: int, rel: bool, fills: bool) -> UpgradeCandidate:
    # item_code is str(code) on BOTH sides, so the string tiebreak is identical.
    return UpgradeCandidate(item_code=str(code), value=float(value), level=level,
                            craft_level=craft, relevant=rel, fills_empty=fills)


def _block(c: UpgradeCandidate) -> list[int]:
    return [int(c.item_code), int(c.value), c.level, c.craft_level,
            1 if c.relevant else 0, 1 if c.fills_empty else 0]


def _chosen(result: UpgradeCandidate | None) -> tuple[str, int] | None:
    return None if result is None else (result.item_code, int(result.value))


def _oracle_chosen(d: dict) -> tuple[str, int] | None:
    return None if not d["present"] else (d["chosen"]["code"], d["chosen"]["value"])


@settings(max_examples=300)
@given(
    inv_present=_BOOL, craft_present=_BOOL,
    iv=_VALUE, il=_LEVEL, ic=_CRAFT, ir=_BOOL, ifl=_BOOL,
    cv=_VALUE, cl=_LEVEL, cc=_CRAFT, cr=_BOOL, cfl=_BOOL,
)
def test_best_by_value_matches_lean(inv_present, craft_present, iv, il, ic, ir, ifl,
                                    cv, cl, cc, cr, cfl):
    inv = _cand(1, iv, il, ic, ir, ifl) if inv_present else None
    craft = _cand(2, cv, cl, cc, cr, cfl) if craft_present else None
    py = best_by_value(inv, craft)
    # arg layout matches the oracle's craftBase = (9 if invPresent else 3): only
    # emit the inventory block (6 ints) when inv is present.
    args = [0, 1 if inv_present else 0, 1 if craft_present else 0]
    if inv_present:
        args += _block(inv)
    if craft_present:
        args += _block(craft)
    lean = run_oracle("upgrade_selection", [args])[0]
    assert _chosen(py) == _oracle_chosen(lean)
    # tie -> inventory pick, locally pinned
    if inv is not None and craft is not None and inv.value == craft.value:
        assert py is inv


@st.composite
def _candidate_lists(draw):
    """A list of candidates over a SMALL item-code domain so codes REPEAT (the
    same item mapped to multiple slots → same-code candidates that tie on the key,
    since the slot is not in the key) and a small value domain so values repeat —
    exercising both the full tiebreak chain and the same-code/equal-key tie."""
    n = draw(st.integers(min_value=1, max_value=6))
    codes = draw(st.lists(st.integers(min_value=0, max_value=4), min_size=n,
                          max_size=n))
    cands = []
    for code in codes:
        cands.append(_cand(code, draw(_VALUE), draw(_LEVEL), draw(_CRAFT),
                           draw(_BOOL), draw(_BOOL)))
    return cands


@settings(max_examples=300)
@given(cands=_candidate_lists(), which=st.sampled_from([1, 2]))
def test_best_by_key_matches_lean(cands, which):
    key = craftable_key if which == 1 else inventory_key
    py = best_by_key(cands, key)
    args = [which, len(cands)]
    for c in cands:
        args += _block(c)
    lean = run_oracle("upgrade_selection", [args])[0]
    assert _chosen(py) == _oracle_chosen(lean)
    # argmax soundness (local): the pick dominates every candidate by the key.
    assert py is not None
    pk = key(py)
    for c in cands:
        assert key(c) <= pk


def test_best_by_key_same_code_tie_first_wins_against_lean():
    """Two SAME-code, equal-KEY candidates (one item, two slots — slot is not in
    the key) tie under both `craftable_key` and `inventory_key`. The argmax keeps
    the FIRST in list order (first-wins) on both sides. The candidates differ only
    in `level` (NOT part of `craftable_key`) so the equal-key tie is genuine, and
    Python returns the FIRST instance by identity."""
    first = _cand(7, 3, 1, 2, True, True)
    second = _cand(7, 3, 9, 2, True, True)  # same code/value/craft/rel/fills; diff level
    assert craftable_key(first) == craftable_key(second)
    py = best_by_key([first, second], craftable_key)
    assert py is first  # first-wins, by identity
    args = [1, 2, *_block(first), *_block(second)]
    lean = run_oracle("upgrade_selection", [args])[0]
    # both pick the same (code, value) pair — the shared tie value.
    assert _chosen(py) == _oracle_chosen(lean) == ("7", 3)

    # inventory_key: level IS in the key, so make a genuine equal-key tie by using
    # equal level and differing only on craft_level (NOT in inventory_key).
    inv_first = _cand(8, 2, 4, 1, False, False)
    inv_second = _cand(8, 2, 4, 9, False, False)
    assert inventory_key(inv_first) == inventory_key(inv_second)
    inv_py = best_by_key([inv_first, inv_second], inventory_key)
    assert inv_py is inv_first
    inv_lean = run_oracle("upgrade_selection",
                          [[2, 2, *_block(inv_first), *_block(inv_second)]])[0]
    assert _chosen(inv_py) == _oracle_chosen(inv_lean) == ("8", 2)


def test_best_by_value_tie_prefers_inventory_against_lean():
    """An equal-value inventory and craftable pick: the OWNED (inventory) item
    wins (cheaper to equip than craft) — pinned against the Lean oracle."""
    inv = _cand(1, 3, 2, 0, True, False)
    craft = _cand(2, 3, 5, 0, True, False)
    py = best_by_value(inv, craft)
    assert py is inv
    lean = run_oracle("upgrade_selection",
                      [[0, 1, 1] + _block(inv) + _block(craft)])[0]
    assert _chosen(py) == _oracle_chosen(lean) == ("1", 3)

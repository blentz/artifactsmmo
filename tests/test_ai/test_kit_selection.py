"""`kit_selection` — which weapon/tool the character is actually WORKING with.

These tests exist for the MEMO. `_pick_tools` was 73% of a timed-out plan.

Measured 2026-08-21 on live C3P0, planning one
`UpgradeEquipment(iron_ring->ring2_slot)`: 15.02s for 902 nodes — 16.6 ms per
NODE — with

    kit_selection._pick_tools           63,732 calls   11.0s cumulative
      equipment.scoring.gather_score  10,856,432 calls
      game_data.item_stats            14,193,484 calls

`inventory_keep.reason_quantity` asks the keep authority on every node
expansion, the keep authority asks which tool is the working one, and that
rescanned the candidate set × every gathering skill each time — with a bag that
barely changes between sibling nodes. `pick_loadout` was memoized in the earlier
planner-CPU work; this selector was missed, and it stayed invisible until
searches got deep enough to hit the 15s budget.
"""

from unittest.mock import patch

import pytest

from artifactsmmo_cli.ai import kit_selection
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd_with_tools() -> GameData:
    """Two tools for two different skills, so a change of bag changes the answer.

    `gather_score` reads `skill_effects[skill]`; more negative is better (the
    game encodes -10 as "10% faster cooldown for this skill").
    """
    gd = GameData()
    gd._item_stats = {
        "copper_pickaxe": ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                                    skill_effects={"mining": -10}),
        "iron_axe": ItemStats(code="iron_axe", level=10, type_="weapon",
                              skill_effects={"woodcutting": -20}),
        "plain_rock": ItemStats(code="plain_rock", level=1, type_="resource"),
    }
    return gd


def test_pick_tools_is_memoized_across_calls() -> None:
    """The same candidate set must not be rescanned. Asserted by COUNTING the
    catalog reads rather than by timing — a timing assertion would be flaky and
    would not say what it means."""
    gd = _gd_with_tools()
    state = make_state(inventory={"copper_pickaxe": 1, "iron_axe": 1})
    reads = {"n": 0}
    real = gd.item_stats

    def counting(code: str):  # type: ignore[no-untyped-def]
        reads["n"] += 1
        return real(code)

    with patch.object(gd, "item_stats", counting):
        first = kit_selection.best_gathering_tools(state, gd)
        after_first = reads["n"]
        second = kit_selection.best_gathering_tools(state, gd)
        after_second = reads["n"]

    assert first == second
    assert after_first > 0, "the first call must actually do the work"
    assert after_second == after_first, "the second call rescanned the catalog"


def test_a_different_bag_is_a_different_answer() -> None:
    """The memo keys on the CANDIDATE SET. Sharing one answer across different
    bags would hand the keep authority the wrong working tool — the hoard bug
    this module exists to prevent."""
    gd = _gd_with_tools()

    with_axe = kit_selection.best_gathering_tools(
        make_state(inventory={"iron_axe": 1}), gd)
    with_pick = kit_selection.best_gathering_tools(
        make_state(inventory={"copper_pickaxe": 1}), gd)

    assert with_axe == {"iron_axe"}
    assert with_pick == {"copper_pickaxe"}


def test_the_memoized_answer_cannot_be_mutated_by_a_caller() -> None:
    """Both callers `return` the value straight out. A memo that hands out
    mutable state is worse than no memo: one caller's `.add()` would corrupt
    every later node."""
    gd = _gd_with_tools()
    state = make_state(inventory={"iron_axe": 1})

    first = kit_selection.best_gathering_tools(state, gd)

    with pytest.raises(AttributeError):
        first.add("copper_pickaxe")  # type: ignore[attr-defined]
    assert kit_selection.best_gathering_tools(state, gd) == first


def test_the_owned_scope_still_ranges_over_the_bank() -> None:
    """The memo must not collapse the two scopes. `best_owned_gathering_tools`
    adds the BANK to the candidate set, and a tool held only in the bank is
    invisible to the bag-scoped selector — an ownership cap fed from the bag
    answer would license melting the character's last tool."""
    gd = _gd_with_tools()
    state = make_state(inventory={"copper_pickaxe": 1}, bank_items={"iron_axe": 1})

    assert kit_selection.best_gathering_tools(state, gd) == {"copper_pickaxe"}
    assert kit_selection.best_owned_gathering_tools(state, gd) == {
        "copper_pickaxe", "iron_axe"}


def test_pick_weapon_is_memoized_too() -> None:
    """The OTHER half of the keep authority's per-node question. With only
    `_pick_tools` memoized this became the top cost of the same search — 229,300
    calls, 4.5 of 15 seconds. Fixing one half of a pair just moves the cost."""
    gd = _gd_with_tools()
    gd._item_stats["bronze_sword"] = ItemStats(
        code="bronze_sword", level=1, type_="weapon", attack={"earth": 12})
    state = make_state(inventory={"bronze_sword": 1, "iron_axe": 1})
    reads = {"n": 0}
    real = gd.item_stats

    def counting(code: str):  # type: ignore[no-untyped-def]
        reads["n"] += 1
        return real(code)

    with patch.object(gd, "item_stats", counting):
        first = kit_selection.best_fighting_weapon(state, gd)
        after_first = reads["n"]
        second = kit_selection.best_fighting_weapon(state, gd)
        after_second = reads["n"]

    assert first == second == "bronze_sword"
    assert after_first > 0
    assert after_second == after_first, "the second call rescanned the catalog"


def test_no_weapon_to_hand_is_a_cached_answer_not_a_miss() -> None:
    """`None` is a REAL answer — "nothing to fight with". Testing the memo with
    `.get(...) is not None` would treat it as a miss and rescan every empty bag,
    which is the common case deep in a gather chain."""
    gd = _gd_with_tools()
    state = make_state(inventory={"plain_rock": 1})
    reads = {"n": 0}
    real = gd.item_stats

    def counting(code: str):  # type: ignore[no-untyped-def]
        reads["n"] += 1
        return real(code)

    with patch.object(gd, "item_stats", counting):
        assert kit_selection.best_fighting_weapon(state, gd) is None
        after_first = reads["n"]
        assert kit_selection.best_fighting_weapon(state, gd) is None
        after_second = reads["n"]

    assert after_second == after_first, "a None answer was not cached"


def test_both_memos_are_bounded() -> None:
    """An unbounded memo on a per-node key is a leak: a long search grows one
    entry per distinct bag state, and a bag differs by one item between siblings.
    BOTH caches are asserted — they evict independently, so a bound on one says
    nothing about the other."""
    gd = _gd_with_tools()

    for i in range(kit_selection._KIT_MEMO_MAX + 50):
        state = make_state(inventory={"iron_axe": 1, f"filler_{i}": 1})
        kit_selection.best_gathering_tools(state, gd)
        kit_selection.best_fighting_weapon(state, gd)

    assert len(kit_selection._TOOL_CACHES.cache_for(gd)) <= kit_selection._KIT_MEMO_MAX
    assert len(kit_selection._WEAPON_CACHES.cache_for(gd)) <= kit_selection._KIT_MEMO_MAX


def test_two_catalogs_do_not_share_answers() -> None:
    """THE BUG THIS KEYING FIXES. The first version keyed on the candidate SET
    alone, so a second `GameData` with the same item CODES was served the first
    one's answers — six `formal/diff/test_bank_selection_diff` failures that each
    passed in isolation and only appeared in a full run.

    Deterministic on purpose: an earlier version of this test asserted that a
    collected catalog drops its caches via `gc.collect()`, which passed bare and
    failed under coverage, because coverage tracing holds the reference. GC
    TIMING is not the property — per-catalog isolation is."""
    first = _gd_with_tools()
    second = _gd_with_tools()
    # same code, different stats: in `second`, the axe helps MINING, not woodcutting
    second._item_stats["iron_axe"] = ItemStats(
        code="iron_axe", level=10, type_="weapon", skill_effects={"mining": -30})
    state = make_state(inventory={"iron_axe": 1, "copper_pickaxe": 1})

    from_first = kit_selection.best_gathering_tools(state, first)
    from_second = kit_selection.best_gathering_tools(state, second)

    assert from_first == {"iron_axe", "copper_pickaxe"}, (
        "woodcutting -> iron_axe, mining -> copper_pickaxe")
    assert from_second == {"iron_axe"}, (
        "in this catalog the axe outranks the pickaxe at MINING and nothing "
        "does woodcutting — a shared memo would have returned the other answer")


def test_each_catalog_gets_its_own_cache() -> None:
    """The keying that makes the isolation above hold."""
    first, second = _gd_with_tools(), _gd_with_tools()
    state = make_state(inventory={"iron_axe": 1})
    kit_selection.best_gathering_tools(state, first)
    kit_selection.best_gathering_tools(state, second)

    assert kit_selection._TOOL_CACHES.cache_for(first) is not \
        kit_selection._TOOL_CACHES.cache_for(second)


def test_a_recycled_address_never_serves_the_previous_catalogs_tools() -> None:
    """The keying above is by `id(game_data)`, and an `id()` is unique only among
    LIVE objects — CPython hands a freed address straight to the next allocation.
    Two catalogs alternating, each freed before the next is built, so the
    allocator recycles the address every round; each must get its OWN answer.

    `CatalogueScope.cache_for`'s `weakref.finalize` is what makes that hold: drop
    it and the second catalog reads the first's tool set."""
    state = make_state(inventory={"iron_axe": 1})
    for round_ in range(200):
        with_axe = _gd_with_tools()
        assert kit_selection.best_gathering_tools(state, with_axe) == {"iron_axe"}, (
            f"round {round_}: served a freed catalog's answer")
        del with_axe

        bare = GameData()   # same code, no stats -> the axe is not a tool here
        assert kit_selection.best_gathering_tools(state, bare) == set(), (
            f"round {round_}: an empty catalog was served the tool catalog's "
            f"answer from a recycled address")
        del bare

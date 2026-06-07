"""select_consumable: overheal-aware lex-argmin consumable picker.

Among inventory items with qty>0 and hp_restore>0, pick the lex-argmin on key
`(overheal_flag, waste, minus_coverage, code)`:
* overheal_flag = 1 if restore > deficit else 0  (a fitting item is always preferred)
* waste = (restore - deficit) if overheal else 0  (smallest overshoot among overhealers)
* minus_coverage = -restore                        (largest restore among fitters)
* code                                             (deterministic final tiebreak)
"""
from artifactsmmo_cli.ai.consumable_selection import select_consumable
from artifactsmmo_cli.ai.game_data import ItemStats


def _stats(**restores: int) -> dict[str, ItemStats]:
    return {
        code: ItemStats(code=code, level=1, type_="consumable", hp_restore=r)
        for code, r in restores.items()
    }


def test_empty_inventory_returns_none():
    assert select_consumable({}, _stats(), 50) is None


def test_no_usable_consumables_returns_none():
    # bread present but qty 0; ore present but hp_restore 0.
    item_stats = {
        "bread": ItemStats(code="bread", level=1, type_="consumable", hp_restore=30),
        "ore": ItemStats(code="ore", level=1, type_="resource", hp_restore=0),
    }
    assert select_consumable({"bread": 0, "ore": 5}, item_stats, 50) is None


def test_item_missing_from_stats_is_skipped():
    # inventory references an item with no ItemStats entry -> skipped, not crash.
    assert select_consumable({"mystery": 3}, _stats(), 50) is None


def test_single_fitting_item_chosen():
    assert select_consumable({"bread": 1}, _stats(bread=30), 50) == ("bread", 30)


def test_prefers_fitting_over_overhealing():
    # deficit 40: bread(30) fits, chicken(80) overheals. Fitter wins despite
    # chicken's larger restore.
    inv = {"bread": 1, "chicken": 1}
    assert select_consumable(inv, _stats(bread=30, chicken=80), 40) == ("bread", 30)


def test_among_fitters_largest_restore_wins():
    # deficit 100: apple(50), bread(30), steak(100) all fit (<= 100). Largest wins.
    inv = {"apple": 1, "bread": 1, "steak": 1}
    assert select_consumable(inv, _stats(apple=50, bread=30, steak=100), 100) == ("steak", 100)


def test_boundary_restore_equals_deficit_is_not_overheal():
    # restore == deficit: NOT overheal (restore > deficit is the flag), and it is
    # the maximal coverage -> chosen over a smaller fitter.
    inv = {"exact": 1, "small": 1}
    assert select_consumable(inv, _stats(exact=50, small=20), 50) == ("exact", 50)


def test_all_overheal_picks_smallest_waste():
    # deficit 10: bread(30) waste 20, chicken(80) waste 70. Least overheal wins.
    inv = {"bread": 1, "chicken": 1}
    assert select_consumable(inv, _stats(bread=30, chicken=80), 10) == ("bread", 30)


def test_all_overheal_tie_on_waste_breaks_on_code():
    # Both items overheal with identical waste (same restore) -> code tiebreak.
    inv = {"b_item": 1, "a_item": 1}
    assert select_consumable(inv, _stats(b_item=80, a_item=80), 10) == ("a_item", 80)


def test_fitter_tie_on_restore_breaks_on_code():
    # Two fitters with the same restore -> smaller code wins.
    inv = {"beta": 1, "alpha": 1}
    assert select_consumable(inv, _stats(beta=40, alpha=40), 100) == ("alpha", 40)


def test_zero_quantity_item_skipped_among_others():
    # chicken would win on coverage but qty 0; bread is the only usable item.
    inv = {"chicken": 0, "bread": 2}
    assert select_consumable(inv, _stats(chicken=100, bread=30), 100) == ("bread", 30)


def test_negative_quantity_skipped():
    inv = {"bread": -1, "apple": 2}
    assert select_consumable(inv, _stats(bread=30, apple=20), 100) == ("apple", 20)


def test_deficit_zero_all_items_overheal_min_waste():
    # deficit 0: every positive-restore item overheals; pick the smallest restore.
    inv = {"big": 1, "small": 1}
    assert select_consumable(inv, _stats(big=80, small=20), 0) == ("small", 20)

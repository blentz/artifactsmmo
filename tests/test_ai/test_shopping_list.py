"""Tests for the bank-aware recipe shopping list core."""

from artifactsmmo_cli.ai.shopping_list import shopping_list

# A copper chain mirroring live game data:
#   copper_dagger -> copper_bar x6 -> copper_ore x10 (raw)
_RECIPES = {
    "copper_dagger": {"copper_bar": 6},
    "copper_bar": {"copper_ore": 10},
}


def test_no_holdings_full_expansion():
    """With nothing owned, the net list is the full recipe requirement."""
    net = shopping_list("copper_dagger", 1, _RECIPES, {})
    assert net == {"copper_dagger": 1, "copper_bar": 6, "copper_ore": 60}


def test_bank_covers_base_material_short_circuits_gather():
    """Banked copper_ore covers all 60 base units -> ore net is 0, the bars and
    dagger still need crafting. This is the live Robby case (485 banked ore)."""
    net = shopping_list("copper_dagger", 1, _RECIPES, {"copper_ore": 485})
    assert net.get("copper_ore", 0) == 0
    assert net["copper_bar"] == 6
    assert net["copper_dagger"] == 1


def test_bank_intermediate_short_circuits_subtree():
    """Banked copper_bar (intermediate) is withdrawn -> the ore subtree below it
    is NOT expanded (no gather work for ore covered by the banked bars)."""
    net = shopping_list("copper_dagger", 1, _RECIPES, {"copper_bar": 6})
    assert net["copper_dagger"] == 1
    assert net.get("copper_bar", 0) == 0
    # All 6 bars came from the bank, so no ore is needed at all.
    assert net.get("copper_ore", 0) == 0


def test_partial_bank_credit_only_deficit_remains():
    """Bank holds 2 of 6 bars -> 4 bars must be crafted -> 40 ore (not 60)."""
    net = shopping_list("copper_dagger", 1, _RECIPES, {"copper_bar": 2})
    assert net["copper_bar"] == 4
    assert net["copper_ore"] == 40


def test_owned_target_makes_everything_zero():
    """Already holding the finished item -> nothing to acquire."""
    net = shopping_list("copper_dagger", 1, _RECIPES, {"copper_dagger": 1})
    assert all(v == 0 for v in net.values())


def test_raw_target():
    """A raw (non-craftable) target with no holdings just needs gathering."""
    net = shopping_list("copper_ore", 5, _RECIPES, {})
    assert net == {"copper_ore": 5}


def test_owned_not_mutated():
    """The caller's owned dict is never mutated (private copy, like min_gathers)."""
    owned = {"copper_ore": 485}
    shopping_list("copper_dagger", 1, _RECIPES, owned)
    assert owned == {"copper_ore": 485}


def test_monotonic_more_bank_never_increases_net():
    """More bank stock never raises any net entry (bank credit only reduces work)."""
    less = shopping_list("copper_dagger", 1, _RECIPES, {"copper_ore": 30})
    more = shopping_list("copper_dagger", 1, _RECIPES, {"copper_ore": 60})
    for item in set(less) | set(more):
        assert more.get(item, 0) <= less.get(item, 0)

"""PURE core of the global gear objective (spec 2026-10-18 §2.3, §2.4). No
GameData/WorldState — plain data only, mirrored by Formal/GearObjective.lean.

Two pieces of the objective live here:

  * the achievable set as a monotone FIXED POINT grown in layers (§2.3):
    layer 0 is what is achievable with no fight-gated drop; each later layer is
    what the union so far newly unlocks (drops of the monsters its loadouts
    beat). The caller supplies `unlock` from game data; this module only grows
    the set and records the layer each item first appears in.
  * the ORDER among missing target pieces (§2.4 step 2): dependency first (the
    item's layer), then gain per unit of acquisition price, then the larger
    gain, then the caller's `slot_rank`. The price only orders the pieces; it
    never changes which piece is the target.
"""

from collections.abc import Callable
from fractions import Fraction

PieceKey = tuple[int, Fraction, Fraction, int]


def achievable_layers(
    base: frozenset[str],
    unlock: Callable[[frozenset[str]], frozenset[str]],
) -> tuple[frozenset[str], ...]:
    """Layer 0 is `base`; layer k+1 is what `unlock` of the union of layers
    0..k adds; the walk stops at the first empty layer. `unlock` must be
    monotone and keep everything it is given: a result that drops an item of
    the union is a caller bug, so it fails loudly instead of shrinking the set.
    The union grows by at least one item per layer, so a finite catalogue
    bounds the number of layers."""
    layers = [base]
    union = base
    while True:
        unlocked = unlock(union)
        assert union <= unlocked, f"unlock shrank the achievable set: lost {sorted(union - unlocked)}"
        fresh = unlocked - union
        if not fresh:
            return tuple(layers)
        layers.append(fresh)
        union = union | fresh


def layer_of(layers: tuple[frozenset[str], ...]) -> dict[str, int]:
    """Map every item to the index of the layer it first appears in. Layers
    from `achievable_layers` are disjoint; an item in two layers is refused."""
    index: dict[str, int] = {}
    for depth, layer in enumerate(layers):
        for item in layer:
            assert item not in index, f"{item} appears in layers {index[item]} and {depth}"
            index[item] = depth
    return index


def piece_order_key(layer: int, gain: Fraction, price: Fraction, slot_rank: int) -> PieceKey:
    """Ascending sort key for a missing target piece: lower layer first
    (dependency), then larger gain per price, then larger gain, then the
    caller's `slot_rank`. `gain` may be 0; a price that is not positive has no
    defined ratio and is refused."""
    assert price > 0, f"piece price must be positive, got {price}"
    return (layer, -(gain / price), -gain, slot_rank)


def objective_held(missing: frozenset[str]) -> bool:
    """The target loadout is held exactly when no piece of it is missing."""
    return not missing

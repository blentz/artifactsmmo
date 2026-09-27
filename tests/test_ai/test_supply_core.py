"""Tests for `obtain_model.supply_core`: the memo's exactness and its work
bound. The walk's answers are pinned against the Lean mirror by
`formal/diff/test_obtain_model_supply_diff.py`."""

from collections.abc import Sequence

from artifactsmmo_cli.ai.obtain_model.supply_core import Supply, can_supply

UNBOUNDED = 10**9


def _craft(*inputs: tuple[str, int]) -> Supply:
    return Supply(1, UNBOUNDED, tuple(inputs))


def test_an_answer_cut_by_the_path_is_not_reused_where_the_path_differs() -> None:
    """`b` is first asked under a path holding `a` (its only way in, cut), then
    directly under the root, where `a` is open: reusing the first answer would
    say no. `a` is gathered as well, so the right answer is yes."""
    supplies = {"root": [_craft(("a", 1), ("b", 1))],
                "a": [_craft(("b", 1)), _craft(("ore", 1))],
                "b": [_craft(("a", 1))],
                "ore": [Supply(1, UNBOUNDED, ())]}
    assert can_supply("root", 1, {}, supplies)


class _Counting(dict[str, Sequence[Supply]]):
    """A supplies table that counts how often the walk expands a node, and
    fails the moment the count passes `limit` (an exponential walk would
    otherwise never return)."""

    expansions = 0
    limit = 0

    def get(self, key: str, default: Sequence[Supply] = ()) -> Sequence[Supply]:  # type: ignore[override]
        _Counting.expansions += 1
        assert _Counting.expansions <= _Counting.limit, "the walk re-expands a shared subtree"
        return super().get(key, default)


def test_a_shared_subtree_is_walked_once_not_once_per_parent() -> None:
    """Forty layers of two items, each needing both items of the layer below,
    bottoming out in gathered items: the answer is yes, so every input of every
    layer is asked, and a walk that re-walks per parent costs 2**40
    expansions. Memoised, it is linear. (A no would not test this: `all` stops
    at the first missing input, so even the naive walk is linear there.)"""
    depth = 40
    supplies = _Counting()
    for layer in range(depth):
        below = [(f"a{layer + 1}", 1), (f"b{layer + 1}", 1)]
        supplies[f"a{layer}"] = [_craft(*below)]
        supplies[f"b{layer}"] = [_craft(*below)]
    supplies[f"a{depth}"] = [Supply(1, UNBOUNDED, ())]
    supplies[f"b{depth}"] = [Supply(1, UNBOUNDED, ())]
    _Counting.expansions = 0
    _Counting.limit = 4 * depth
    assert can_supply("a0", 1, {}, supplies)

"""Differential test: `optimal_buy_mix_pure` (Python) == `optimalBuyMix` (Lean)
over random recipes/budgets through the `optimal_buy_mix` oracle kind.

Locks the float-free "largest affordable craft batch" core --
`max { B <= max_batch : sum_i price_i * max(0, B*need_i - held_i) <= gold }` -- to
its kernel-checked Nat mirror. The oracle takes a length-prefixed list
`[gold, max_batch, n, need_0, held_0, price_0, ...]` (budget and cap first, then
`n` `[need, held, price]` records), so the test sends ONE request and reads
result `[0]`.

Sampling follows the brief: `n` in `[1,3]`, `needs` in `[1,4]` (real recipes have
positive ingredient quantities), `held` in `[0,20]` (incl. 0 so a full deficit is
bought), `prices` in `[1,10]`, `gold` in `[0,200]`, `max_batch` in `[1,20]`. The
`@example` anchors pin the exact-budget tie (feasibility `<=` -> `<` flip) and the
real-deficit case (the `b*need - held` -> `held - b*need` sign flip), which the
two kept mutants diverge on.
"""
from hypothesis import example, given, settings, strategies as st

from artifactsmmo_cli.ai.optimal_buy_mix import optimal_buy_mix_pure
from formal.diff.oracle_client import run_oracle

_ingredient = st.tuples(
    st.integers(min_value=1, max_value=4),    # need (>= 1, real recipe quantity)
    st.integers(min_value=0, max_value=20),   # held (incl. 0 -> full deficit)
    st.integers(min_value=1, max_value=10),   # price
)


def _oracle_args(recipe: list[tuple[int, int, int]], gold: int,
                 max_batch: int) -> list[int]:
    """Flatten into the oracle's `[gold, max_batch, n, need, held, price, ...]`."""
    args: list[int] = [gold, max_batch, len(recipe)]
    for need, held, price in recipe:
        args.extend([need, held, price])
    return args


# Exact-budget tie: cost(2) == gold == 4 on need1/held0/price2 -> largest affordable
# is 2. The `<=` -> `<` feasibility flip breaks at B=2 and returns 1 instead.
@example(recipe=[(1, 0, 2)], gold=4, max_batch=20)
# Real deficit with batch>=1 unaffordable: cost(1)=8 > gold 3 -> answer 0. The
# `b*need - held` -> `held - b*need` sign flip makes every deficit non-positive, so
# the mutant reports cost 0 and buys the full max_batch.
@example(recipe=[(4, 0, 2)], gold=3, max_batch=20)
@settings(max_examples=500, deadline=None)
@given(
    recipe=st.lists(_ingredient, min_size=1, max_size=3),
    gold=st.integers(min_value=0, max_value=200),
    max_batch=st.integers(min_value=1, max_value=20),
)
def test_optimal_buy_mix_matches_lean(recipe, gold, max_batch):
    needs = [need for need, _, _ in recipe]
    held = [h for _, h, _ in recipe]
    prices = [p for _, _, p in recipe]
    py = optimal_buy_mix_pure(needs, held, prices, gold, max_batch)
    lean = run_oracle("optimal_buy_mix", [_oracle_args(recipe, gold, max_batch)])[0]
    assert lean["batch"] == py

"""Differential test: RecipeCostMemo.full_cost must equal a fresh closure_demand
call over random valid acyclic recipe DAGs.

We call the LIVE `closure_demand` function (not inlining its math) so that this
test pins the memo to the already-proved function — no new Lean theorem needed.
Pattern follows test_recipe_closure_diff.py: random DAGs over int item codes,
encoded as string keys in a minimal GameData stub.
"""

import random

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import closure_demand
from artifactsmmo_cli.ai.recipe_cost_memo import RecipeCostMemo


def _gd(recipes: dict[int, dict[int, int]]) -> GameData:
    gd = GameData()
    gd._crafting_recipes = {str(k): {str(s): q for s, q in v.items()}
                            for k, v in recipes.items()}
    return gd


def _acyclic_recipe_graph(rng: random.Random) -> tuple[dict[int, dict[int, int]], int]:
    """Random acyclic recipe DAG over item codes 0..n-1.

    Edges only go from lower to higher codes (strict acyclicity). Returns
    (recipes, target_item). Some items may be raw (no recipe).
    """
    n = rng.randint(1, 8)
    items = list(range(n))
    recipes: dict[int, dict[int, int]] = {}
    for it in items:
        if rng.random() < 0.5:
            n_sub = rng.randint(1, 3)
            subs: dict[int, int] = {}
            for _ in range(n_sub):
                if it + 1 > n - 1:
                    continue
                sub = rng.randint(it + 1, n - 1)
                subs[sub] = rng.randint(1, 5)
            if subs:
                recipes[it] = subs
    target = rng.choice(items)
    return recipes, target


@settings(max_examples=300, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_memo_equals_closure_demand(seed: int) -> None:
    """memo.full_cost(item) == fresh closure_demand(item, 1, gd, {}, frozenset())."""
    rng = random.Random(seed)
    recipes, target = _acyclic_recipe_graph(rng)

    gd = _gd(recipes)
    target_str = str(target)

    # Ground truth: live closure_demand (already proved in Lean).
    expected: dict[str, int] = {}
    closure_demand(target_str, 1, gd, expected, frozenset())

    # Memo result must be identical in value.
    memo = RecipeCostMemo(gd)
    result = memo.full_cost(target_str)

    assert result == expected, (
        f"memo != closure_demand: recipes={recipes} target={target} "
        f"result={result} expected={expected}"
    )

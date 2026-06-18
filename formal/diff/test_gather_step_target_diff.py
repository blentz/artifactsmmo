"""The live `gather_step_target` (Python) must agree with
`Formal.StepDispatch.gatherTarget` (Lean) on the routed (code, qty) — the Piece-C
feasibility decision that, for a depth-UNREACHABLE equippable root, routes the
GatherMaterials goal to the strategy's deepest actionable step instead of the deep
root recipe (which explodes the planner).

Both sides compute `min_gathers(root, 1, recipes, owned)` and compare it to
`equip_max_depth`: ≤ ⇒ keep the root target `(root, 1)`; > ⇒ route to
`(step, step_qty)`. Faithfulness (P3d): BOTH sides thread and CONSUME the
`owned` holdings depth-first — the Lean `minGathers` was aligned to the Python
consume semantics, closing the P2c-class constant-credit gap — so the generator
samples DAG recipes (a child may be claimed by MULTIPLE parents), the exact
domain where the pre-P3d constant-credit model double-credited shared stock.
The DAG double-credit and diamond witnesses are pinned deterministically.
"""
import random

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.gather_step_target import gather_step_target
from artifactsmmo_cli.ai.min_gathers import min_gathers
from formal.diff.oracle_client import run_oracle

_N = 6


def _make_dag(seed: int) -> dict[int, dict[int, int]]:
    """Random DAG recipe over items 0..N-1 (children strictly greater —
    acyclic — and a child may be claimed by MULTIPLE parents: the shape that
    distinguishes consume from constant-credit accounting). Item 0 is the
    root equippable."""
    rng = random.Random(seed)
    recipes: dict[int, dict[int, int]] = {}
    for item in range(_N):
        free = list(range(item + 1, _N))
        rng.shuffle(free)
        k = rng.randint(0, min(3, len(free)))
        if k == 0:
            continue
        recipes[item] = {j: rng.randint(1, 4) for j in free[:k]}
    return recipes


def _raw_leaf(recipes: dict[int, dict[int, int]]) -> int:
    """A raw-leaf item code (no recipe) to use as the deepest step; falls back to
    the highest index (always a leaf in the increasing-index DAG)."""
    for i in range(_N - 1, -1, -1):
        if not recipes.get(i):
            return i
    return _N - 1


def _oracle_args(recipes, owned, root, step, step_qty, max_depth,
                 max_yield=1) -> list[int]:
    triples: list[int] = []
    n = 0
    for parent, recipe in recipes.items():
        for sub, per in recipe.items():
            triples.extend([parent, sub, per])
            n += 1
    owned_pairs: list[int] = []
    no = 0
    for code, q in owned.items():
        owned_pairs.extend([code, q])
        no += 1
    return [n, *triples, no, *owned_pairs, root, step, step_qty, max_depth, max_yield]


@settings(max_examples=400, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=10_000),
    owned_seed=st.integers(min_value=0, max_value=10_000),
    step_qty=st.integers(min_value=0, max_value=40),
    max_depth=st.integers(min_value=0, max_value=200),
    max_yield=st.integers(min_value=1, max_value=5),
)
def test_routed_target_matches_lean(seed, owned_seed, step_qty, max_depth, max_yield):
    recipes = _make_dag(seed)
    rng = random.Random(owned_seed)
    owned = {i: rng.randint(0, 12) for i in range(_N) if rng.random() < 0.5}
    root = 0
    step = _raw_leaf(recipes)
    py_code, py_qty = gather_step_target(
        root, step, step_qty, recipes, owned, max_depth, max_yield)
    lean = run_oracle(
        "gather_step_target",
        [_oracle_args(recipes, owned, root, step, step_qty, max_depth, max_yield)],
    )[0]
    assert (lean["code"], lean["qty"]) == (py_code, py_qty), (
        recipes, owned, step_qty, max_depth, max_yield, (py_code, py_qty), lean)


def test_unreachable_root_routes_to_step():
    """Deep from-scratch chain (480 ore) over budget -> route to the raw step.
    Deterministic kill for the raw-leaf-contributes-nothing mutant (cost 0
    would keep the root)."""
    recipes = {0: {1: 6}, 1: {2: 8}, 2: {3: 10}}  # boots<-bar6<-ironbar8<-ore10
    owned: dict[int, int] = {}
    py = gather_step_target(0, 3, 480, recipes, owned, 15)
    assert py == (3, 480)
    lean = run_oracle("gather_step_target", [_oracle_args(recipes, owned, 0, 3, 480, 15)])[0]
    assert (lean["code"], lean["qty"]) == py


def test_reachable_root_keeps_root():
    """Holdings cover the chain -> root cost 0 <= budget -> keep (root, 1).
    Deterministic kill for the never-credit (`used = 0`) mutant (cost 480
    would route to the step)."""
    recipes = {0: {1: 6}, 1: {2: 8}, 2: {3: 10}}
    owned = {1: 6}  # 6 of item-1 cover the root recipe -> 0 gathers
    assert min_gathers(0, 1, recipes, owned) == 0
    py = gather_step_target(0, 3, 480, recipes, owned, 15)
    assert py == (0, 1)
    lean = run_oracle("gather_step_target", [_oracle_args(recipes, owned, 0, 3, 480, 15)])[0]
    assert (lean["code"], lean["qty"]) == py


def test_boundary_at_budget_keeps_root():
    """root_cost == max_depth is reachable (strict-> gate) -> keep root."""
    recipes = {0: {1: 15}}
    owned: dict[int, int] = {}
    assert min_gathers(0, 1, recipes, owned) == 15
    py = gather_step_target(0, 1, 15, recipes, owned, 15)
    assert py == (0, 1)
    lean = run_oracle("gather_step_target", [_oracle_args(recipes, owned, 0, 1, 15, 15)])[0]
    assert (lean["code"], lean["qty"]) == py


def test_dag_double_credit_witness_routes_to_step():
    """THE P3d divergence witness: two parents share the raw material 3; the
    single held unit covers only ONE branch, so the consume cost is 1 > 0 and
    BOTH sides route to the step. The pre-P3d constant-credit model counted 0
    (the held unit credited under both parents) and would have kept the root —
    the deterministic kill for the never-consume (`owned[item] = held`)
    mutant."""
    recipes = {0: {1: 1, 2: 1}, 1: {3: 1}, 2: {3: 1}}
    owned = {3: 1}
    assert min_gathers(0, 1, recipes, owned) == 1
    py = gather_step_target(0, 3, 1, recipes, owned, 0)
    assert py == (3, 1)
    lean = run_oracle("gather_step_target", [_oracle_args(recipes, owned, 0, 3, 1, 0)])[0]
    assert (lean["code"], lean["qty"]) == py


def test_dag_diamond_one_path_covered():
    """Diamond: both paths need 2 of the shared raw 3; the 2 held units cover
    the FIRST path only -> consume cost 2 (constant credit said 0). Budget 1
    sits strictly between, so the routing decision itself separates the two
    accountings on both sides."""
    recipes = {0: {1: 1, 2: 1}, 1: {3: 2}, 2: {3: 2}}
    owned = {3: 2}
    assert min_gathers(0, 1, recipes, owned) == 2
    py = gather_step_target(0, 3, 2, recipes, owned, 1)
    assert py == (3, 2)
    lean = run_oracle("gather_step_target", [_oracle_args(recipes, owned, 0, 3, 2, 1)])[0]
    assert (lean["code"], lean["qty"]) == py


def test_partial_credit_keeps_root():
    """Partially held intermediate: 3 of 8 bars held -> only the 5-bar deficit
    expands (cost 50 <= 60 -> keep root). Deterministic kill for the
    ignore-credit-in-recursion (`per_unit * qty`) mutant (cost 80 would route
    to the step)."""
    recipes = {0: {1: 8}, 1: {2: 10}}
    owned = {1: 3}
    assert min_gathers(0, 1, recipes, owned) == 50
    py = gather_step_target(0, 2, 50, recipes, owned, 60)
    assert py == (0, 1)
    lean = run_oracle("gather_step_target", [_oracle_args(recipes, owned, 0, 2, 50, 60)])[0]
    assert (lean["code"], lean["qty"]) == py


def test_multi_yield_divides_cost_keeps_root():
    """THE multi-yield witness: a 16-unit chain is over budget at yield 1
    (16 > 15 -> route to step) but the resource drops 2 per gather, so the real
    cost is ceil(16/2)=8 <= 15 and the root is kept. Both sides must apply the
    `maxYield` divisor (ceilGathers); deterministic kill for the
    drop-the-divisor (`maxYield := 1`) mutant, which would route to the step."""
    recipes = {0: {1: 16}}
    owned: dict[int, int] = {}
    assert min_gathers(0, 1, recipes, owned) == 16
    py = gather_step_target(0, 1, 16, recipes, owned, 15, 2)
    assert py == (0, 1)
    lean = run_oracle(
        "gather_step_target", [_oracle_args(recipes, owned, 0, 1, 16, 15, 2)])[0]
    assert (lean["code"], lean["qty"]) == py
    # And at yield 1 it still routes to the step (the over-count path).
    py1 = gather_step_target(0, 1, 16, recipes, owned, 15, 1)
    assert py1 == (1, 16)
    lean1 = run_oracle(
        "gather_step_target", [_oracle_args(recipes, owned, 0, 1, 16, 15, 1)])[0]
    assert (lean1["code"], lean1["qty"]) == py1

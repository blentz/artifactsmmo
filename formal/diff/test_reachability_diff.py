"""Differential + invariant test for the PRODUCTION ASSERT in `strategy.decide`:

```
if not is_reachable(root, ...): continue
step = actionable_step(root, ...)
assert step is not None          # strategy.py:251
```

The two functions use DIFFERENT cycle-trackers — `is_reachable` a per-DFS-path
`path` frozenset (backtracks), `actionable_step` a single MUTABLE `visited` set
shared across ALL recursive branches (never un-marks). The Lean proof
(`Formal.StrategyTraversal.reachable_implies_actionable`) shows the assert is safe
for WELL-FORMED graphs; this test LOCKS the real Python shared-`visited`
`actionable_step` to that invariant over random graphs (cycles, satisfied-interior
nodes, deep chains) AND cross-checks both functions against the Lean oracle.

WELL-FORMEDNESS (a genuine property of `prerequisites`/`_producible`, not a rig):
* an `obtain` node with NONEMPTY direct prereqs is producible — nonempty prereqs
  come from a crafting recipe, and a recipe ⇒ `_producible`.
We GENERATE only well-formed graphs (the only graphs the production code builds)
and assert the invariant; we ALSO generate arbitrary graphs to confirm the Python
two-tracker functions still match the Lean oracle there.

Graph wiring matches test_strategy_traversal_diff.py: `prerequisites` /
`_producible` are DEPENDENCIES (the graph INPUT), substituted to encode the graph;
the functions under test (`is_reachable`, `actionable_step`) are NOT stubbed.
"""
import random

from hypothesis import given, settings, strategies as st
from pytest import MonkeyPatch

from artifactsmmo_cli.ai.tiers import strategy
from artifactsmmo_cli.ai.tiers.meta_goal import (
    ObtainItem,
    ReachCharLevel,
)
from formal.diff.oracle_client import run_oracle

KIND_OBTAIN, KIND_CHAR = 0, 2


class _Graph:
    def __init__(self, n, kinds, sat, prod, prereqs):
        self.n = n
        self.kinds = kinds
        self.sat = sat
        self.prod = prod
        self.prereqs = prereqs

    def node(self, i):
        if self.kinds[i] == KIND_OBTAIN:
            return ObtainItem(str(i))
        return ReachCharLevel(i)

    def id_of(self, node):
        if isinstance(node, ObtainItem):
            return int(node.code)
        return int(node.level)


def _install(graph, mp):
    def fake_prerequisites(node, state, game_data, recoverable=None, exclude_recycle_leaf=False):
        return [graph.node(p) for p in graph.prereqs[graph.id_of(node)]]

    def fake_producible(code, state, game_data):
        return graph.prod[int(code)]

    def make_is_sat(g):
        def _is_sat(self, state, game_data):
            return g.sat[g.id_of(self)]
        return _is_sat

    mp.setattr(strategy, "prerequisites", fake_prerequisites)
    mp.setattr(strategy, "_producible", fake_producible)
    mp.setattr(ObtainItem, "is_satisfied", make_is_sat(graph))
    mp.setattr(ReachCharLevel, "is_satisfied", make_is_sat(graph))


def _encode(graph, root, fuel):
    args = [graph.n]
    for i in range(graph.n):
        pre = graph.prereqs[i]
        args += [1 if graph.sat[i] else 0, 1 if graph.prod[i] else 0,
                 graph.kinds[i], len(pre)] + list(pre)
    args += [root, fuel]
    return args


def _make_wellformed(graph):
    """Coerce a graph to the production invariant in-place: obtain-with-prereqs ⇒
    producible."""
    for i in range(graph.n):
        if graph.kinds[i] == KIND_OBTAIN and graph.prereqs[i]:
            graph.prod[i] = True           # nonempty prereqs come from a recipe
    return graph


def _rand_graph(rng, allow_cycle, deep):
    n = rng.randint(1, 7) if not deep else rng.randint(5, 9)
    kinds, sat, prod, prereqs = {}, {}, {}, {}
    for i in range(n):
        r = rng.random()
        kinds[i] = KIND_OBTAIN if r < 0.75 else KIND_CHAR
        prod[i] = rng.random() < 0.5
        subs = []
        # deep chains: link i -> i+1 to force long unmet chains
        link_p = 0.9 if deep else 0.6
        if rng.random() < link_p:
            for _ in range(rng.randint(1, 3)):
                if allow_cycle:
                    mat = rng.randint(0, n - 1)
                else:
                    if i + 1 > n - 1:
                        continue
                    mat = rng.randint(i + 1, n - 1)
                if mat != i or allow_cycle:
                    subs.append(mat)
        prereqs[i] = subs
    for i in range(n):
        sat[i] = rng.random() < 0.35
    root = rng.choice(range(n))
    sat[root] = False
    fuel = 2 * n + 4
    return _Graph(n, kinds, sat, prod, prereqs), root, fuel


@settings(max_examples=250, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_reachable_implies_actionable_wellformed(seed):
    """THE INVARIANT on WELL-FORMED graphs (what the production code builds):
    the real Python `is_reachable` (per-DFS-path frozenset) returning True
    implies the real Python `actionable_step` (also per-DFS-path frozenset,
    post-Phase-13 refactor — byte-equivalent to the proved Lean `actStep`)
    returns a node — never None. A failure here would be the production crash bug."""
    rng = random.Random(seed)
    allow_cycle = rng.random() < 0.5
    deep = rng.random() < 0.4
    graph, root, fuel = _rand_graph(rng, allow_cycle, deep)
    _make_wellformed(graph)

    state, game_data = object(), object()
    root_node = graph.node(root)

    with MonkeyPatch.context() as mp:
        _install(graph, mp)
        py_reach = strategy.is_reachable(root_node, state, game_data)
        py_step = strategy.actionable_step(root_node, state, game_data)

    ctx = (f"n={graph.n} root={root} cycle={allow_cycle} deep={deep} "
           f"kinds={graph.kinds} sat={graph.sat} prod={graph.prod} "
           f"prereqs={graph.prereqs}")
    if py_reach:
        assert py_step is not None, (
            f"PRODUCTION ASSERT VIOLATED (reachable but no step): {ctx}")

    # cross-check both functions against the proved Lean oracle on this graph.
    args = _encode(graph, root, fuel)
    lean_reach = run_oracle("strategy_is_reachable", [args])[0]["is_reachable"]
    lean_act = run_oracle("strategy_actionable", [args])[0]["actionable"]
    assert py_reach == lean_reach, f"is_reachable mismatch: {ctx} lean={lean_reach}"
    py_none = py_step is None
    assert py_none == (lean_act is None), (
        f"actionable none-agreement: {ctx} lean={lean_act}")


@settings(max_examples=250, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_two_tracker_match_oracle_arbitrary(seed):
    """Even on ARBITRARY (not-necessarily-well-formed) graphs, the Python
    is_reachable/actionable_step two-tracker functions match the Lean oracle on
    reachability and the none/some verdict. (No invariant claim off the
    well-formed fragment.)"""
    rng = random.Random(seed)
    allow_cycle = rng.random() < 0.5
    graph, root, fuel = _rand_graph(rng, allow_cycle, deep=False)

    state, game_data = object(), object()
    root_node = graph.node(root)
    with MonkeyPatch.context() as mp:
        _install(graph, mp)
        py_reach = strategy.is_reachable(root_node, state, game_data)
        py_step = strategy.actionable_step(root_node, state, game_data)

    args = _encode(graph, root, fuel)
    lean_reach = run_oracle("strategy_is_reachable", [args])[0]["is_reachable"]
    lean_act = run_oracle("strategy_actionable", [args])[0]["actionable"]
    ctx = (f"n={graph.n} root={root} cycle={allow_cycle} kinds={graph.kinds} "
           f"sat={graph.sat} prod={graph.prod} prereqs={graph.prereqs}")
    assert py_reach == lean_reach, f"is_reachable mismatch: {ctx} lean={lean_reach}"
    assert (py_step is None) == (lean_act is None), (
        f"actionable none-agreement: {ctx} lean={lean_act} py={py_step}")


# ---------------------------------------------------------------------------
# Anchored well-formed cases the suspected bug would have hit.
# ---------------------------------------------------------------------------

def test_diamond_shared_leaf_reachable_has_step():
    """Diamond: root 0 -> {1, 2}; both 1 and 2 -> {3}; 3 a producible obtain leaf.
    is_reachable=True (3 grounds both branches). actionable_step returns a step
    (3 is actionable — returned on first reach via either branch under the
    per-DFS-path frozenset tracker)."""
    g = _Graph(4, {0: KIND_OBTAIN, 1: KIND_OBTAIN, 2: KIND_OBTAIN, 3: KIND_OBTAIN},
               {0: False, 1: False, 2: False, 3: False},
               {0: True, 1: True, 2: True, 3: True},
               {0: [1, 2], 1: [3], 2: [3], 3: []})
    state, gd = object(), object()
    with MonkeyPatch.context() as mp:
        _install(g, mp)
        assert strategy.is_reachable(g.node(0), state, gd) is True
        assert strategy.actionable_step(g.node(0), state, gd) is not None


def test_dead_sibling_then_shared_actionable():
    """root 0 -> {1, 2}; branch 1 -> {3} where 3 is a NON-producible obtain leaf
    (dead, blocks branch 1's step); branch 2 -> {4}, 4 producible leaf. Branch 1
    is explored first, marking node 3 visited and returning None for that prereq.
    But is_reachable needs ALL prereqs reachable: node 3 not producible ⇒ 1 not
    reachable ⇒ 0 not reachable, so decide skips it (no assert). Confirms the
    consistency: when actionable_step would have trouble, is_reachable is False."""
    g = _Graph(5,
               {0: KIND_OBTAIN, 1: KIND_OBTAIN, 2: KIND_OBTAIN, 3: KIND_OBTAIN, 4: KIND_OBTAIN},
               {0: False, 1: False, 2: False, 3: False, 4: False},
               {0: True, 1: True, 2: True, 3: False, 4: True},
               {0: [1, 2], 1: [3], 2: [4], 3: [], 4: []})
    state, gd = object(), object()
    with MonkeyPatch.context() as mp:
        _install(g, mp)
        # node 3 non-producible leaf -> branch 1 unreachable -> root unreachable
        assert strategy.is_reachable(g.node(0), state, gd) is False
        # invariant vacuously holds (guard would skip); step may be None and that's fine

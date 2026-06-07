"""Differential test: the real Python `strategy_traversal` PURE CORE
(`is_reachable`, `unmet_closure_size`, `actionable_step`, `root_cost`) must agree
with the proved Lean oracle over random node graphs — including CYCLES,
SATISFIED-INTERIOR nodes, and unsatisfiable leaves.

We exercise the genuine TRAVERSAL logic by controlling the abstract node graph:
* monkeypatch `strategy.prerequisites` to return a node→prereqs map;
* monkeypatch each `MetaGoal.is_satisfied` to a controlled per-node bool;
* monkeypatch `strategy._producible` to a controlled per-node bool.

Nodes are `Nat` ids. Each id maps to a real `MetaGoal` so `isinstance` dispatch
(ObtainItem / ReachSkillLevel / ReachCharLevel = the `kind`) is faithful:
* obtain id i → `ObtainItem(str(i))`
* skill  id i → `ReachSkillLevel(str(i), 1)`
* char   id i → `ReachCharLevel(i)`   (distinct levels; is_satisfied is patched)

The SAME graph is encoded for the Lean oracle (flat ints). The satisfied-interior
pruning is exercised by marking some INTERIOR (non-root, with prereqs) nodes
satisfied: the Python DFS visits but does NOT descend/count them, and the Lean
model mirrors this — the assertion closes the historical TLA+-era gap.
"""
import random

from hypothesis import given, settings, strategies as st
from pytest import MonkeyPatch

from artifactsmmo_cli.ai.tiers import strategy
from artifactsmmo_cli.ai.tiers.meta_goal import (
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from formal.diff.oracle_client import run_oracle

# kind codes match the Lean oracle: 0 = obtain, 1 = skill, 2 = char
KIND_OBTAIN, KIND_SKILL, KIND_CHAR = 0, 1, 2


class _Graph:
    """A controlled abstract node graph over ids 0 .. n-1."""

    def __init__(self, n, kinds, sat, prod, prereqs):
        self.n = n
        self.kinds = kinds          # id -> kind code
        self.sat = sat              # id -> bool
        self.prod = prod            # id -> bool
        self.prereqs = prereqs      # id -> list[int]

    def node(self, i):
        k = self.kinds[i]
        if k == KIND_OBTAIN:
            return ObtainItem(str(i))
        if k == KIND_SKILL:
            return ReachSkillLevel(str(i), 1)
        return ReachCharLevel(i)

    def id_of(self, node):
        if isinstance(node, ObtainItem):
            return int(node.code)
        if isinstance(node, ReachSkillLevel):
            return int(node.skill)
        return int(node.level)


def _install(graph, mp):
    """Wire the controlled graph into the strategy module + MetaGoal classes."""

    def fake_prerequisites(node, state, game_data):
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
    mp.setattr(ReachSkillLevel, "is_satisfied", make_is_sat(graph))
    mp.setattr(ReachCharLevel, "is_satisfied", make_is_sat(graph))


def _encode(graph, root, fuel):
    args = [graph.n]
    for i in range(graph.n):
        pre = graph.prereqs[i]
        args += [1 if graph.sat[i] else 0, 1 if graph.prod[i] else 0,
                 graph.kinds[i], len(pre)] + list(pre)
    args += [root, fuel]
    return args


def _rand_graph(rng, allow_cycle):
    n = rng.randint(1, 7)
    kinds, sat, prod, prereqs = {}, {}, {}, {}
    for i in range(n):
        # mostly obtain (exercises closure/producible); some skill/char
        r = rng.random()
        kinds[i] = KIND_OBTAIN if r < 0.7 else (KIND_SKILL if r < 0.85 else KIND_CHAR)
        prod[i] = rng.random() < 0.5
        subs = []
        if rng.random() < 0.6:
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
    # satisfaction: root usually unmet; mark some INTERIOR nodes satisfied to
    # exercise the satisfied-interior pruning (visited but not descended/counted).
    for i in range(n):
        sat[i] = rng.random() < 0.35
    root = rng.choice(range(n))
    # the real `actionable_step` / wrapper is only ever entered on an UNMET root
    # (the strategy `decide` skips satisfied roots); keep the root unmet so the
    # actionable soundness precondition holds.
    sat[root] = False
    return _Graph(n, kinds, sat, prod, prereqs), root, 2 * n + 4


@settings(max_examples=240, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_strategy_traversal_matches_lean(seed):
    rng = random.Random(seed)
    allow_cycle = rng.random() < 0.5
    graph, root, fuel = _rand_graph(rng, allow_cycle)

    state = object()        # unused: every read is monkeypatched
    game_data = object()
    root_node = graph.node(root)

    with MonkeyPatch.context() as mp:
        _install(graph, mp)
        py_reach = strategy.is_reachable(root_node, state, game_data)
        py_closure = strategy.unmet_closure_size(root_node, state, game_data)
        py_step = strategy.actionable_step(root_node, state, game_data)
        py_step_id = graph.id_of(py_step) if py_step is not None else None

    args = _encode(graph, root, fuel)
    reach = run_oracle("strategy_is_reachable", [args])[0]["is_reachable"]
    closure = run_oracle("strategy_closure_size", [args])[0]["closure_size"]
    actionable = run_oracle("strategy_actionable", [args])[0]["actionable"]

    ctx = (f"n={graph.n} root={root} cycle={allow_cycle} kinds={graph.kinds} "
           f"sat={graph.sat} prod={graph.prod} prereqs={graph.prereqs}")

    assert py_reach == reach, f"is_reachable mismatch: {ctx} lean={reach}"
    assert py_closure == closure, f"closure_size mismatch: {ctx} lean={closure}"

    # actionable: agree on none/some; when some, BOTH returned nodes are actionable
    # (the DFS pick-order is implementation-defined — assert membership, not identity).
    py_none = py_step_id is None
    lean_none = actionable is None
    assert py_none == lean_none, f"actionable none-agreement: {ctx} lean={actionable} py={py_step_id}"
    if not py_none:
        assert _is_actionable(graph, py_step_id), f"py step not actionable: {ctx}"
        assert _is_actionable(graph, actionable), f"lean step not actionable: {ctx} a={actionable}"


def _is_actionable(graph, i):
    """A node is actionable iff unmet ∧ all direct prereqs satisfied ∧
    (kind=obtain ⇒ producible)."""
    if graph.sat[i]:
        return False
    if any(not graph.sat[p] for p in graph.prereqs[i]):
        return False
    if graph.kinds[i] == KIND_OBTAIN and not graph.prod[i]:
        return False
    return True


@settings(max_examples=200, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_root_cost_matches_lean(seed):
    """`root_cost`: char/skill = max(1, target − have); gear = unmet_closure_size."""
    rng = random.Random(seed)
    graph, root, fuel = _rand_graph(rng, rng.random() < 0.5)
    game_data = object()
    kind = graph.kinds[root]

    with MonkeyPatch.context() as mp:
        _install(graph, mp)
        if kind == KIND_CHAR:
            target = rng.randint(1, 40)
            have = rng.randint(1, 40)
            root_node = ReachCharLevel(target)

            class _S:
                level = have
            py = strategy.root_cost(root_node, _S(), game_data)
            args = _encode_root_cost(graph, root, fuel, KIND_CHAR, target, have)
        elif kind == KIND_SKILL:
            target = rng.randint(1, 40)
            have = rng.randint(1, 40)
            root_node = ReachSkillLevel(str(root), target)

            class _S:
                skills = {str(root): have}
                level = 1
            py = strategy.root_cost(root_node, _S(), game_data)
            args = _encode_root_cost(graph, root, fuel, KIND_SKILL, target, have)
        else:
            root_node = graph.node(root)
            py = strategy.root_cost(root_node, object(), game_data)
            args = _encode_root_cost(graph, root, fuel, KIND_OBTAIN, 0, 0)

    lean = run_oracle("strategy_root_cost", [args])[0]["root_cost"]
    assert py == lean, f"root_cost mismatch: kind={kind} py={py} lean={lean}"
    assert lean >= 1


def _encode_root_cost(graph, root, fuel, kind, target, have):
    args = [graph.n]
    for i in range(graph.n):
        pre = graph.prereqs[i]
        args += [1 if graph.sat[i] else 0, 1 if graph.prod[i] else 0,
                 graph.kinds[i], len(pre)] + list(pre)
    args += [root, fuel, kind, target, have]
    return args


# ---------------------------------------------------------------------------
# Anchored cases (cycles + satisfied-interior pruning)
# ---------------------------------------------------------------------------

def test_cycle_unreachable_and_none():
    """A 2-cycle of unmet obtain nodes (neither producible): not reachable, no step."""
    g = _Graph(2, {0: KIND_OBTAIN, 1: KIND_OBTAIN},
               {0: False, 1: False}, {0: False, 1: False}, {0: [1], 1: [0]})
    state, gd = object(), object()
    with MonkeyPatch.context() as mp:
        _install(g, mp)
        assert strategy.is_reachable(g.node(0), state, gd) is False
        assert strategy.actionable_step(g.node(0), state, gd) is None
    args = _encode(g, 0, 8)
    assert run_oracle("strategy_is_reachable", [args])[0]["is_reachable"] is False
    assert run_oracle("strategy_actionable", [args])[0]["actionable"] is None


def test_satisfied_interior_pruning():
    """Root 0 (unmet) has prereqs 1 (SATISFIED interior, whose prereq 3 is never
    reached) and 2 (unmet, producible leaf). closure counts {0,2}=2; the
    satisfied node 1 is visited but neither counted nor descended."""
    g = _Graph(4, {0: KIND_OBTAIN, 1: KIND_OBTAIN, 2: KIND_OBTAIN, 3: KIND_OBTAIN},
               {0: False, 1: True, 2: False, 3: False},
               {0: True, 1: True, 2: True, 3: True},
               {0: [1, 2], 1: [3], 2: [], 3: []})
    state, gd = object(), object()
    with MonkeyPatch.context() as mp:
        _install(g, mp)
        assert strategy.unmet_closure_size(g.node(0), state, gd) == 2
        py_step = strategy.actionable_step(g.node(0), state, gd)
        py_step_id = g.id_of(py_step)
    args = _encode(g, 0, 8)
    assert run_oracle("strategy_closure_size", [args])[0]["closure_size"] == 2
    assert py_step_id == 2          # unmet, no unmet prereqs, producible
    assert run_oracle("strategy_actionable", [args])[0]["actionable"] == 2

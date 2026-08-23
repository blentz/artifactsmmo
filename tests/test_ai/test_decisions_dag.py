"""O2: the decision graph is acyclic (spec §3.5).

`MAX_RESOLVE_DEPTH = 32` raises rather than truncating, which is the right
RUNTIME behaviour but is detection, not proof — it fires on the character whose
cycle it is, in production, after 32 wasted resolutions. The honest discharge is
static: enumerate every `Decision` class under `ai/decisions/`, read the set of
`Decision` types each one's body can HAND BACK, and assert that relation is a
DAG. The edges are Python control flow, not a modelled relation, so this is a
reflection test rather than a Lean theorem — and worth more than a theorem here
for exactly that reason.

Two anti-vacuity guards, because "an assertion over a collection that is empty
for unrelated reasons" is one of this epic's named decorative-test mechanisms:

* `test_the_sweep_sees_the_whole_graph` pins a lower bound on the number of
  classes AND edges discovered, and names one class from each module. A sweep
  that quietly discovered nothing would otherwise pass forever.
* `test_a_cycle_is_detected` runs the SAME two functions over the real classes
  plus a pair of mutually-returning test-local ones, so the detector is proved
  to fail on a real cycle rather than assumed to.
"""
import ast
import importlib
import inspect
import pkgutil
import textwrap

import artifactsmmo_cli.ai.decisions as decisions_pkg
from artifactsmmo_cli.ai.decision import Decision
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

# Floors, not exact counts: a new Decision must not have to touch this file,
# but a sweep that goes blind must. `decisions/obtain_item.py` holds six
# classes and five edges; `decisions/root.py` holds five and four.
_MIN_CLASSES = 11
_MIN_EDGES = 9


def _decision_classes() -> list[type]:
    """Every concrete `Decision` subclass defined under `ai/decisions/`."""
    found: dict[str, type] = {}
    for info in pkgutil.iter_modules(decisions_pkg.__path__):
        module = importlib.import_module(f"{decisions_pkg.__name__}.{info.name}")
        for obj in vars(module).values():
            if (isinstance(obj, type) and issubclass(obj, Decision)
                    and obj is not Decision
                    and obj.__module__ == module.__name__
                    and not inspect.isabstract(obj)):
                found[obj.__name__] = obj
    return sorted(found.values(), key=lambda cls: cls.__name__)


def static_child_edges(classes: list[type]) -> dict[str, set[str]]:
    """`class name -> the Decision classes its source can hand back`.

    Read from the AST of each class, not from a type annotation: an
    annotation says `Decision[Leaf] | Leaf | None` on every node and would
    make the relation the complete graph.

    EVERY `Name(...)` call anywhere in the class body counts as an edge when
    that name is one of the swept classes — not only calls that sit inside a
    `return`. Fix-round-1: scoping the walk to `ast.Return` UNDER-approximated
    and the docstring claimed the opposite. The two-line idiom

        child = IsThereACombatTarget(...)
        return child

    hides an edge from a return-scoped walk, and `strategy_driver.py:639`
    already writes `resolve_node` exactly that way, so this is a shape the
    codebase uses rather than a hypothetical. Walking every call is strictly
    over-approximating: it can only ever ADD edges, so it cannot miss a cycle,
    and a spurious edge fails loudly rather than passing silently.
    """
    names = {cls.__name__ for cls in classes}
    edges: dict[str, set[str]] = {}
    for cls in classes:
        tree = ast.parse(textwrap.dedent(inspect.getsource(cls)))
        edges[cls.__name__] = {
            node.func.id for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in names}
    return edges


def find_cycle(edges: dict[str, set[str]]) -> list[str] | None:
    """One cycle in `edges` as an ordered path, or None when it is a DAG."""
    done: set[str] = set()
    path: list[str] = []
    on_path: set[str] = set()

    def visit(node: str) -> list[str] | None:
        if node in on_path:
            return [*path[path.index(node):], node]
        if node in done:
            return None
        path.append(node)
        on_path.add(node)
        for child in sorted(edges.get(node, set())):
            cycle = visit(child)
            if cycle is not None:
                return cycle
        path.pop()
        on_path.remove(node)
        done.add(node)
        return None

    for start in sorted(edges):
        cycle = visit(start)
        if cycle is not None:
            return cycle
    return None


def test_the_sweep_sees_the_whole_graph():
    classes = _decision_classes()
    names = {cls.__name__ for cls in classes}
    edges = static_child_edges(classes)
    assert len(classes) >= _MIN_CLASSES, names
    assert sum(len(v) for v in edges.values()) >= _MIN_EDGES, edges
    # Named pins, so the floors above cannot be met by one module alone.
    assert "CanIAffordTheCurrencyLeaf" in names
    assert "IsMyGearBehindMyTier" in names
    assert edges["IsMyGearBehindMyTier"] == {"IsThereACombatTarget",
                                             "WhichSlotIsFurthestBehind"}


def test_the_decision_graph_is_acyclic():
    edges = static_child_edges(_decision_classes())
    assert find_cycle(edges) is None


class _CycleUp(Decision[Goal]):
    """Half of a deliberate two-node cycle. Never resolved — the sweep reads
    its SOURCE, so the bodies only have to name each other."""

    name = "_CycleUp"

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision[Goal] | Goal | None":
        return _CycleDown()


class _CycleDown(Decision[Goal]):
    """The other half."""

    name = "_CycleDown"

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision[Goal] | Goal | None":
        return _CycleUp()


def test_a_cycle_is_detected():
    """The same two functions the acyclicity test uses, over the real classes
    plus a cyclic pair. If this passed, `test_the_decision_graph_is_acyclic`
    would be asserting nothing."""
    classes = [*_decision_classes(), _CycleUp, _CycleDown]
    cycle = find_cycle(static_child_edges(classes))
    assert cycle is not None
    assert set(cycle) == {"_CycleUp", "_CycleDown"}
    assert cycle[0] == cycle[-1]


class _WrappedChild(Decision[Goal]):
    """Hands its child back through a local instead of straight out of the
    `return`. Fix-round-1 regression pin: the old return-scoped walk could not
    see this edge, and `strategy_driver.py:639` writes `resolve_node` in
    exactly this shape, so it is a real idiom and not a hypothetical."""

    name = "_WrappedChild"

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision[Goal] | Goal | None":
        child = _CycleUp()
        return child


def test_an_edge_handed_back_through_a_local_is_still_an_edge():
    edges = static_child_edges([_WrappedChild, _CycleUp, _CycleDown])
    assert edges["_WrappedChild"] == {"_CycleUp"}


def test_a_self_edge_is_a_cycle():
    """A node that can return itself is the one-node case the path-based
    walk has to catch separately from the two-node case above."""
    assert find_cycle({"A": {"A"}}) == ["A", "A"]

"""The joint-walk census (Phase 2d-L1 of docs/PLAN_decision_architecture_redesign.md).

The one walk (`ai/decompose_core`) answers "can `qty` of `item` be had"
JOINTLY: sibling inputs that share a material draw on one bag and one set of
route capacities. It is GREEDY: a usable route is taken even when a later
sibling then goes short, so a yes is sound but a no can be false (holding an
extra item can make an earlier route usable that spends what a sibling needed).
The walk it replaced asked every input against the whole bag and could say yes
to a tree it could not finish.

This census keeps both effects visible on the catalogue. For every craftable
recipe, in two holdings (an empty bag; and one recipe run's worth of every
direct ingredient in the tree, not summed across the craftables that use it, so
a material shared between branches is short for all of them), it asks three
questions of the same walk graph:

  * INDEPENDENT: each input against the whole bag (the replaced semantics);
  * GREEDY: the production walk;
  * EXACT: the joint walk with every route both used (when usable) and skipped,
    a bounded search over the choices the greedy walk commits to.

and classifies the cell:

  * AGREE: all three say the same;
  * SHARED_SHORTAGE: the independent walk says yes, the exact joint no; the old
    walk over-promised and the joint one answers correctly;
  * GREEDY_FALSE_NEGATIVE: the exact joint walk says yes, the greedy one no;
  * SEARCH_CAPPED: the exact search passed its state bound (no verdict).

Report-only: SHARED_SHORTAGE and GREEDY_FALSE_NEGATIVE are counted, not gated
(the greedy contract accepts false negatives). The EXACT search is a verifier
for this census; production never runs it.
"""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum

from artifactsmmo_cli.ai.craft_plan_gen import DECOMPOSE_POLICY
from artifactsmmo_cli.ai.decompose_core import Route, can_obtain, runs
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.recipe_closure import recipe_closure
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.audit.craft_census import craftable_recipes
from artifactsmmo_cli.audit.craft_completeness import census_state, craft_grid

EXACT_STATE_BOUND = 5000
"""End states the exact search may hold at once before it gives up on a cell."""

type _Bag = tuple[tuple[str, int], ...]
type _Used = tuple[tuple[tuple[str, int], int], ...]
type _State = tuple[_Bag, _Used]


class JointGap(Enum):
    AGREE = "agree"
    SHARED_SHORTAGE = "shared_shortage"
    GREEDY_FALSE_NEGATIVE = "greedy_false_negative"
    SEARCH_CAPPED = "search_capped"


@dataclass(frozen=True)
class JointCell:
    recipe: str
    holding: str
    independent: bool
    greedy: bool
    exact: bool | None
    gap: JointGap


class SearchCapped(Exception):
    """The exact search passed `EXACT_STATE_BOUND`."""


def independent_can(item: str, qty: int, on_hand: Mapping[str, int],
                    routes: Mapping[str, Sequence[Route[str]]],
                    path: frozenset[str] = frozenset()) -> bool:
    """The replaced semantics: every input of every route is asked against the
    whole bag, so siblings sharing a material each count all of it."""
    have = on_hand.get(item, 0)
    if have >= qty:
        return True
    if item in path:
        return False
    remaining = qty - have
    for route in routes.get(item, ()):
        if remaining == 0:
            break
        take = min(route.capacity, remaining)
        if take <= 0:
            continue
        n = runs(take, route.yield_per)
        if all(independent_can(m, n * per, on_hand, routes, path | {item}) for m, per in route.inputs):
            remaining -= take
    return remaining == 0


def _freeze(bag: Mapping[str, int], used: Mapping[tuple[str, int], int]) -> _State:
    return (tuple(sorted((k, v) for k, v in bag.items() if v)),
            tuple(sorted((k, v) for k, v in used.items() if v)))


class _Exact:
    """The joint walk with each usable route both taken and skipped."""

    def __init__(self, routes: Mapping[str, Sequence[Route[str]]]) -> None:
        self._routes = routes

    def can(self, item: str, qty: int, st: _State, path: frozenset[str]) -> Iterator[_State]:
        bag, used = dict(st[0]), dict(st[1])
        have = bag.get(item, 0)
        if have >= qty:
            bag[item] = have - qty
            yield _freeze(bag, used)
            return
        if item in path:
            return
        bag[item] = 0
        yield from self._fill(item, list(self._routes.get(item, ())), 0, qty - have,
                              _freeze(bag, used), path | {item})

    def _fill(self, item: str, routes: list[Route[str]], index: int, deficit: int, st: _State,
              inner: frozenset[str]) -> Iterator[_State]:
        if deficit == 0:
            yield st
            return
        if index == len(routes):
            return
        route = routes[index]
        used = dict(st[1])
        take = min(route.capacity - used.get((item, index), 0), deficit)
        if take > 0:
            used[(item, index)] = used.get((item, index), 0) + take
            spent: _State = (st[0], _freeze({}, used)[1])
            for after in self._feed(route.inputs, runs(take, route.yield_per), spent, inner):
                yield from self._fill(item, routes, index + 1, deficit - take, after, inner)
        yield from self._fill(item, routes, index + 1, deficit, st, inner)

    def _feed(self, inputs: Sequence[tuple[str, int]], n: int, st: _State,
              inner: frozenset[str]) -> Iterator[_State]:
        states = {st}
        for material, per in inputs:
            nxt: set[_State] = set()
            for s in states:
                nxt.update(self.can(material, n * per, s, inner))
                if len(nxt) > EXACT_STATE_BOUND:
                    raise SearchCapped
            states = nxt
        yield from states


def exact_can(item: str, qty: int, on_hand: Mapping[str, int],
              routes: Mapping[str, Sequence[Route[str]]]) -> bool:
    """Is there ANY use-or-skip choice of routes under which the joint walk
    has `qty` of `item`? Raises `SearchCapped` past the state bound."""
    start = _freeze(on_hand, {})
    return next(iter(_Exact(routes).can(item, qty, start, frozenset())), None) is not None


def _one_run_each(recipe: str, game_data: GameData) -> dict[str, int]:
    """One run's worth of every direct ingredient of every craftable in
    `recipe`'s tree, taking the largest single use (never the sum)."""
    _resources, craftables = recipe_closure(game_data, [recipe])
    held: dict[str, int] = {}
    for code in craftables | {recipe}:
        for material, per in (game_data.crafting_recipe(code) or {}).items():
            held[material] = max(held.get(material, 0), per)
    return held


def classify(independent: bool, greedy: bool, exact: bool | None) -> JointGap:
    if exact is None:
        return JointGap.SEARCH_CAPPED
    if exact and not greedy:
        return JointGap.GREEDY_FALSE_NEGATIVE
    if independent and not exact:
        return JointGap.SHARED_SHORTAGE
    return JointGap.AGREE


HOLDINGS = ("empty", "one_run_each")


def run_cell(recipe: str, holding: str, game_data: GameData) -> JointCell:
    """One recipe at its at-skill, highest-level census cell, in one holding."""
    cell = max(craft_grid(recipe, game_data), key=lambda c: (c.skill_level, c.char_level))
    state = census_state(recipe, cell, game_data)
    if holding == "one_run_each":
        state = replace(state, inventory=_one_run_each(recipe, game_data))
    model = ObtainModel(state, game_data, NO_PROFILE_CONTEXT, datetime.now(UTC))
    graph = model.walk_graph(recipe, DECOMPOSE_POLICY, keep=frozenset({recipe}))
    independent = independent_can(recipe, 1, graph.on_hand, graph.routes)
    greedy = can_obtain(recipe, 1, graph.on_hand, graph.routes)
    exact: bool | None
    try:
        exact = exact_can(recipe, 1, graph.on_hand, graph.routes)
    except SearchCapped:
        exact = None
    return JointCell(recipe, holding, independent, greedy, exact, classify(independent, greedy, exact))


def run_census(game_data: GameData) -> list[JointCell]:
    return [run_cell(recipe, holding, game_data)
            for recipe in craftable_recipes(game_data) for holding in HOLDINGS]


def summary_line(cells: Sequence[JointCell]) -> str:
    counts = {gap: sum(1 for c in cells if c.gap is gap) for gap in JointGap}
    return (f"{len(cells)} cells; " + ", ".join(f"{gap.value} {n}" for gap, n in counts.items()))


def render_matrix(cells: Sequence[JointCell]) -> str:
    """The census document: the summary, then every cell that is not AGREE."""
    lines = ["# Joint-walk census", "",
             "> Generated by `scripts/gen_joint_walk.py` from the committed bundle. "
             "See `audit/joint_walk_census.py` for the classes.", "",
             summary_line(cells), "",
             "| Recipe | Holding | Independent | Greedy | Exact | Class |",
             "|---|---|---|---|---|---|"]
    lines += [f"| {c.recipe} | {c.holding} | {c.independent} | {c.greedy} | {c.exact} | {c.gap.value} |"
              for c in cells if c.gap is not JointGap.AGREE]
    return "\n".join(lines) + "\n"

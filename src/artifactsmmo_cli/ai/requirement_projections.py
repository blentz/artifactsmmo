"""Projections over `RequirementGraph` — Wave 2 of the unification epic.

`docs/superpowers/specs/2026-07-19-requirement-model-unification-epic.md` §4.3.

Each projection is the single answer that replaces one of the disagreeing walks.
**Nothing consumes them yet**; Waves 3-8 swap consumers over one at a time.

| Projection            | Replaces                            | Axis 1  | Axis 2     |
|-----------------------|-------------------------------------|---------|------------|
| `requirement_edges`   | `prerequisites` body                | edges   | truncation |
| `requirement_closure` | `recipe_closure`                    | closure | none       |
| `demand_set`          | `closure_demand` + `objective_needs`| closure | none       |
| `skill_gates`         | ALL FOUR of D3                      | closure | none       |

The two axes stay EXPLICIT (§4.2). They are legitimate differences that must
SURVIVE unification, not drift to be collapsed:

* **Axis 1 edges-vs-closure** — `requirement_edges` is one ply because
  `tiers/strategy.py` does its own traversal on top; collapsing it breaks
  `act_step`.
* **Axis 2 state truncation** — supplied as a `truncate_at` PREDICATE rather
  than baked in, so state-awareness is a pass over the graph and the graph
  itself stays state-free.

`need_set` is deliberately absent — see `requirement_graph`'s module docstring,
deviation 3.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from artifactsmmo_cli.ai.recipe_closure import _closure_demand
from artifactsmmo_cli.ai.requirement_graph import DemandSet, RequirementGraph


def _fuel(graph: RequirementGraph) -> int:
    """The proved-sufficient bound from the extracted core: one ply per recipe
    plus one. Kept identical to `len(recipes) + 1` so the Lean bound carries
    over unchanged (`docs/PLAN_mechanical_extraction.md:93`, P4c)."""
    return len(graph.edges) + 1


def requirement_edges(
    graph: RequirementGraph,
    item: str,
    truncate_at: Callable[[str], bool] | None = None,
) -> dict[str, int]:
    """Direct ingredients of `item` — ONE PLY (axis 1).

    `truncate_at` is axis 2 made explicit: when it returns True for `item`, the
    item is a LEAF and its recipe is not opened. That is exactly what
    `prerequisites` does when a ready non-craft source exists (withdraw,
    licensed recycle, live gather, located vendor, winnable drop) — but it is
    now the CALLER's state predicate, so the graph stays state-free.

    Passing no predicate gives the untruncated one-ply answer.
    """
    if truncate_at is not None and truncate_at(item):
        return {}
    return dict(graph.edges.get(item, {}))


def requirement_closure(
    graph: RequirementGraph,
    roots: Iterable[str],
    truncate_at: Callable[[str], bool] | None = None,
) -> frozenset[str]:
    """Every item transitively required by `roots`, roots included.

    ITEM namespace throughout — this is the D1 fix. `recipe_closure` returns
    `copper_rocks` (a resource node) where this returns `copper_ore` (the item),
    so the answer composes with every other walk without a translation step.

    Drop-only materials ARE included — the D2 fix. The two-set return this
    replaces could not represent them, so callers grew three separate patches.

    Cycle-safe: an item already on the walk is not reopened.
    """
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        item = stack.pop()
        if item in seen:
            continue
        seen.add(item)
        for ingredient in requirement_edges(graph, item, truncate_at):
            if ingredient not in seen:
                stack.append(ingredient)
    return frozenset(seen)


def requirement_craftables(
    graph: RequirementGraph,
    roots: Iterable[str],
) -> frozenset[str]:
    """Closure items that have a crafting recipe — the exact replacement for
    `recipe_closure`'s second return (`craftable_mats`).

    Item namespace. Verified BYTE-EQUAL to `recipe_closure(gd, roots)[1]` over
    all 321 bundle recipes before this replaced its five callers, so the swap is
    a pure indirection onto the shared model, not a behaviour change.
    """
    return frozenset(i for i in requirement_closure(graph, roots) if i in graph.edges)


def requirement_gather_skills(
    graph: RequirementGraph,
    roots: Iterable[str],
) -> frozenset[str]:
    """The gathering-skill NAMES needed to gather the closure's gatherable
    materials.

    Replaces the resource-node loop `{resource_skill_level(res)[0] for res in
    needed_resources}` that read `recipe_closure`'s FIRST return. The graph is
    item-namespace (the D1 fix), so it reads the item-keyed `gather_skill`
    directly instead of walking resource nodes. Verified BYTE-EQUAL to that loop
    over all 321 bundle recipes.
    """
    return frozenset(
        graph.gather_skill[item][0]
        for item in requirement_closure(graph, roots)
        if item in graph.gather_skill
    )


def demand_set(
    graph: RequirementGraph,
    roots: Iterable[str],
    quantities: dict[str, int] | None = None,
    yields: dict[str, int] | None = None,
) -> DemandSet:
    """Quantified transitive demand for `roots`.

    Delegates the arithmetic to the extracted core's `_closure_demand` (§4.5) —
    the ceil-batch yield math is proved there, and reimplementing it here would
    move the code out from under `Extracted/RecipeClosure.lean`. This projection
    adds only the root fan-out and the value-type wrapper.

    `quantities` gives per-root multipliers (default 1 each). Quantities across
    roots combine at their MAX, matching `_closure_demand`'s cumulative
    semantics — see `DemandSet.merge`.

    `yields` defaults to the graph's own yields (`game_data.craft_yields`), NOT
    an empty map. That default is load-bearing: the bundle has 31 items with
    Y>1, and ignoring them over-orders their materials at any multiplier >1. It
    is exactly what the live `closure_demand` reads by default, so the projection
    matches it byte-for-byte.
    """
    root_list = list(roots)
    wanted = quantities or {}
    effective_yields = graph.yields if yields is None else yields
    # graph.edges is read-only here (`_closure_demand` only reads recipes), so
    # no defensive copy — this is a hot planner path.
    edges = graph.edges
    out: dict[str, int] = {}
    for root in root_list:
        _closure_demand(_fuel(graph), root, wanted.get(root, 1),
                        edges, effective_yields, {}, out)
    return DemandSet(quantities=out, roots=frozenset(root_list))


def skill_gates(
    graph: RequirementGraph,
    roots: Iterable[str],
    skills: dict[str, int],
) -> dict[str, int]:
    """The UNMET craft-skill gates over the closure of `roots`.

    This is the D3 fix: four derivations existed over the same closure, none
    sharing code, disagreeing on output type — a `{skill: SkillGate}` map, a
    bare `frozenset[str]` of names, a single worst `(skill, current, required)`,
    and one more. This returns `{skill: highest required level}` over every item
    in the closure whose gate the character has not met, which carries strictly
    more than the name-set and is order-independent by construction (a max over
    a set, so D4's `dict`-iteration-order dependence cannot arise).

    An empty result means nothing in the closure is skill-blocked.
    """
    gates: dict[str, int] = {}
    for item in requirement_closure(graph, roots):
        gate = graph.craft_skill.get(item)
        if gate is None:
            continue
        skill, required = gate
        if skills.get(skill, 0) >= required:
            continue
        if required > gates.get(skill, 0):
            gates[skill] = required
    return gates

"""O6 and O8: how a `Decision` may price, and what it may not branch on.

O6 — no `Decision` prices anything except through `route_price`.
O8 — no `Decision` branches on a `SourceKind`.

Both are properties of the same package and both are AST sweeps over it, so they
share one census rather than two that could disagree about which files count.

Wave 6 obligation O6. The resolution graph must have ONE cost model. A node that
prices a candidate by importing `acquisition_cost` directly is a second one, and
a second cost model is how the two halves of a ranking drift apart — the exact
shape `combat_deficit` had, where a production consumer of `acquisition_actions`
was invisible to its own name because it arrived through a `cost_of` callback.

WHAT IS FORBIDDEN, AND WHERE
----------------------------
Every module under `ai/decisions/` is forbidden to import any pricing producer.
`decisions/route.py` is the single permitted exception — it IS the funnel. The
rule is checked on the import graph rather than on call sites because an import
is what a grep can find and a callback is not.

The `Callable` rule is the callback half of the same hole: a `Decision` that
accepts an injected pricer takes a cost model as a parameter, which puts the
model outside this census's reach. Wave 4's `WhichSlotClosesTheFight` makes one
textual call to `deficit_upgrade_target` that prices 22 candidates behind a
closure — permitted, because the closure it injects is built FROM `route_price`,
and forbidden to become a parameter of the node itself.

WHAT WOULD MAKE THIS CENSUS VACUOUS
-----------------------------------
Discovering no `Decision` classes at all — the same failure `test_decisions_dag`
guards with `_MIN_CLASSES`. So this census carries its own floors and fails when
the package it sweeps has fewer classes than the graph is known to contain. A
census that passes because it looked at nothing is worse than no census: it
reports a green obligation over an empty set.

WHY O8 EXISTS
-------------
A `SourceKind` names HOW something is obtained — withdraw, craft, gather, buy,
GE fill, drop. A `Decision` that branches on one is deciding by route, and the
route is the acquisition model's business: it already ranks those options by
cost. A node that prefers, say, CRAFT over BUY is a second opinion about a
question `obtain_sources` has already answered, and it is invisible to the cost
model — the same shape as a second pricer, expressed as a branch instead of a
number.

TWO WAYS TO EVADE IT, AND THE SWEEP RESOLVES BOTH. The design names them: a
`SourceKind` imported under an ALIAS, and a route kind compared by its `.value`
STRING. Attribute access alone would miss `SK.BUY`, and an enum-name scan alone
would miss `== "buy"`. So the sweep tracks the local binding of the import and
also matches the member VALUES, and both evasions have their own positive
control.

The positive controls live in the test module: a synthetic `Decision` that
imports a forbidden producer, or branches on a route kind, must be DETECTED by
the same function that sweeps production.
"""

import ast
import pathlib

PRICING_PRODUCERS: frozenset[str] = frozenset({
    "acquisition_cost",
    "acquisition_cost_core",
    "min_plan_length",
    "bid_vs_craft",
    "learning.projections",
})
"""Modules that produce a cost. Importing one under `ai/decisions/` is a second
cost model unless the importer is the funnel itself."""

ROUTE_KIND_NAMES: frozenset[str] = frozenset({
    "WITHDRAW", "RECYCLE", "CRAFT", "GATHER", "BUY", "GE_FILL", "DROP", "SELL",
})
"""`SourceKind` members by NAME. Duplicated from the enum deliberately: this
census must keep working when the enum grows, and
`test_the_route_kind_vocabulary_is_complete` fails the day it does — a sweep
that silently missed a new member would report a green obligation over an
incomplete alphabet."""

ROUTE_KIND_VALUES: frozenset[str] = frozenset({
    "withdraw", "recycle", "craft", "gather", "buy", "ge_fill", "drop", "sell",
})
"""The same members by VALUE, because `kind == "buy"` evades an attribute scan
entirely. One of the two evasions the design names."""

FUNNEL = "route.py"
"""The ONE module permitted to import a pricing producer."""

MIN_DECISION_CLASSES = 13
"""Floor on `Decision` subclasses found, so the sweep cannot pass by finding
nothing. Raised with the graph: wave 3 shipped five root nodes, wave 4 added
`IsAFightBlockingMe` and `WhichSlotClosesTheFight`. Mirrors
`test_decisions_dag._MIN_CLASSES`."""


def _module_names(node: ast.Import | ast.ImportFrom) -> list[str]:
    """Dotted module names an import statement pulls in.

    Typed to the two node kinds the caller actually passes, so there is no
    third branch to defend against. An `ast.stmt` signature invited a
    `return []` fallthrough that could never execute — dead defensive code the
    coverage gate correctly refused to accept.
    """
    if isinstance(node, ast.Import):
        return [a.name for a in node.names]
    return [node.module] if node.module else []


def _forbidden_in(module: str) -> str | None:
    """The pricing producer `module` names, or None.

    Suffix-matched on dotted segments so `artifactsmmo_cli.ai.acquisition_cost`
    and a bare `acquisition_cost` both resolve, without `acquisition_cost_core`
    being read as `acquisition_cost`.
    """
    for producer in PRICING_PRODUCERS:
        parts = producer.split(".")
        segments = module.split(".")
        if segments[-len(parts):] == parts:
            return producer
    return None


def _returns_a_number(ann: ast.expr | None) -> bool:
    """Does this annotation describe a callable returning a number?

    `Callable[[...], int]` / `[..., float]`. The shape wave 6 §2.2 forbids as a
    `Decision` parameter — an injected pricer is a cost model this census cannot
    see.
    """
    if not isinstance(ann, ast.Subscript):
        return False
    base = ann.value
    name = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", "")
    if name != "Callable":
        return False
    sl = ann.slice
    if not isinstance(sl, ast.Tuple) or len(sl.elts) != 2:
        return False
    ret = sl.elts[1]
    return getattr(ret, "id", None) in {"int", "float"}


def _route_kind_mentions(node: ast.expr) -> str | None:
    """A route kind named by this expression, or None.

    Matched on the UNPARSED source of the expression rather than on a tracked
    import binding, which resolves all three ways to say it with one rule:

      * `SourceKind.BUY`             — the direct form;
      * `SK.BUY`                     — an ALIASED import (evasion 1);
      * `source_kind.SourceKind.BUY` — a plain module import (a third form the
        design did not name, and one a binding-tracker gave up on);
      * `"buy"`                      — the member's VALUE (evasion 2).

    An earlier version tracked the local binding structurally and had a branch
    for the module-import case that simply returned None — it looked like
    handling and was giving up. The coverage gate found it unexercised, which is
    what made the gap visible.

    A bare `.BUY` on some unrelated object is not matched: the attribute form
    requires the enum's own name somewhere in the dotted path.
    """
    if isinstance(node, ast.Constant) and node.value in ROUTE_KIND_VALUES:
        return repr(node.value)
    if isinstance(node, ast.Attribute) and node.attr in ROUTE_KIND_NAMES:
        text = ast.unparse(node)
        head = text.rsplit(".", 1)[0]
        # `SourceKind.BUY` -> head "SourceKind"; `SK.BUY` -> head "SK".
        # An alias is accepted because the import that created it is what makes
        # it an enum reference, and a node that says `SK.BUY` is branching on a
        # route kind whatever the alias is called.
        if head:
            return text
    return None


def _route_kind_branches(tree: ast.Module, path_name: str) -> list[str]:
    """Comparisons inside `tree` that test a route kind.

    Only COMPARISONS count, not every mention: a module may legitimately name a
    `SourceKind` when constructing one or annotating a type. Deciding BY it is
    the defect, and a comparison is what deciding looks like.
    """
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for side in [node.left, *node.comparators]:
            hit = _route_kind_mentions(side)
            if hit is not None:
                found.append(f"{path_name}:{node.lineno} branches on {hit}")
    return found


def sweep(package: pathlib.Path) -> dict[str, list[str]]:
    """Residuals for O6 over every module under `package`.

    Returns a dict with three keys, each a list of human-readable findings:
    `second_pricer` (a forbidden import outside the funnel), `injected_pricer`
    (a `Callable[..., number]` parameter on a `Decision` method), and
    `decision_classes` (every `Decision` subclass seen, for the floor).
    """
    second_pricer: list[str] = []
    injected_pricer: list[str] = []
    route_kind_branch: list[str] = []
    decision_classes: list[str] = []

    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        route_kind_branch.extend(_route_kind_branches(tree, path.name))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if path.name == FUNNEL:
                    continue
                for module in _module_names(node):
                    hit = _forbidden_in(module)
                    if hit is not None:
                        second_pricer.append(
                            f"{path.name}:{node.lineno} imports {hit}")
            if isinstance(node, ast.ClassDef):
                bases = [getattr(b, "id", None) or getattr(
                    getattr(b, "value", None), "id", None) for b in node.bases]
                sub = any(b == "Decision" for b in bases) or any(
                    isinstance(b, ast.Subscript)
                    and getattr(b.value, "id", None) == "Decision"
                    for b in node.bases)
                if sub:
                    decision_classes.append(f"{path.name}:{node.name}")
                    for item in node.body:
                        if not isinstance(item, (ast.FunctionDef,
                                                 ast.AsyncFunctionDef)):
                            continue
                        for arg in item.args.args + item.args.kwonlyargs:
                            if _returns_a_number(arg.annotation):
                                injected_pricer.append(
                                    f"{path.name}:{item.lineno} "
                                    f"{node.name}.{item.name}({arg.arg})")
    return {"second_pricer": second_pricer,
            "injected_pricer": injected_pricer,
            "route_kind_branch": route_kind_branch,
            "decision_classes": decision_classes}


def render(results: dict[str, list[str]]) -> str:
    """One line per residual, plus the floor, in the shape the other censuses
    print so a CI log reads the same way."""
    lines = [
        f"O6_SECOND_PRICER {len(results['second_pricer'])}",
        f"O6_INJECTED_PRICER {len(results['injected_pricer'])}",
        f"O8_ROUTE_KIND_BRANCH {len(results['route_kind_branch'])}",
        f"decision_classes {len(results['decision_classes'])} "
        f"(floor {MIN_DECISION_CLASSES})",
    ]
    lines += [f"  ! {r}" for r in results["second_pricer"]]
    lines += [f"  ! {r}" for r in results["injected_pricer"]]
    lines += [f"  ! {r}" for r in results["route_kind_branch"]]
    return "\n".join(lines)
